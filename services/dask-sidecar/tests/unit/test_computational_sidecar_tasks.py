# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=no-member
# pylint: disable=too-many-instance-attributes

import asyncio
import json
import logging
import re
import threading
from collections.abc import AsyncIterator, Callable, Iterable

# copied out from dask
from dataclasses import dataclass
from pprint import pformat
from random import randint
from typing import Any
from unittest import mock

import distributed
import fsspec
import pytest
from common_library.json_serialization import json_dumps
from dask_task_models_library.container_tasks.docker import DockerBasicAuth
from dask_task_models_library.container_tasks.errors import (
    ServiceInputsUseFileToKeyMapButReceivesZipDataError,
    ServiceRuntimeError,
)
from dask_task_models_library.container_tasks.events import TaskProgressEvent
from dask_task_models_library.container_tasks.io import (
    FileUrl,
    TaskInputData,
    TaskOutputData,
    TaskOutputDataSchema,
)
from dask_task_models_library.container_tasks.protocol import (
    ContainerTaskParameters,
    TaskOwner,
)
from faker import Faker
from models_library.basic_types import EnvVarKey
from models_library.rabbitmq_messages import LoggerRabbitMessage
from models_library.services import ServiceMetaDataPublished
from models_library.services_resources import BootMode
from packaging import version
from pydantic import AnyUrl, SecretStr, TypeAdapter
from pytest_mock.plugin import MockerFixture
from pytest_simcore.helpers.typing_env import EnvVarsDict
from servicelib.rabbitmq._client import RabbitMQClient
from servicelib.rabbitmq._constants import BIND_TO_ALL_TOPICS
from settings_library.s3 import S3Settings
from simcore_service_dask_sidecar.computational_sidecar.docker_utils import (
    LEGACY_SERVICE_LOG_FILE_NAME,
)
from simcore_service_dask_sidecar.computational_sidecar.errors import (
    ServiceBadFormattedOutputError,
)
from simcore_service_dask_sidecar.computational_sidecar.models import (
    LEGACY_INTEGRATION_VERSION,
    ImageLabels,
)
from simcore_service_dask_sidecar.utils.dask import _DEFAULT_MAX_RESOURCES
from simcore_service_dask_sidecar.utils.files import (
    _s3fs_settings_from_s3_settings,
)
from simcore_service_dask_sidecar.worker import run_computational_sidecar
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_delay,
    wait_fixed,
)

_logger = logging.getLogger(__name__)

pytest_simcore_core_services_selection = [
    "rabbit",
]


@pytest.fixture()
def dask_subsystem_mock(
    mocker: MockerFixture, create_rabbitmq_client: Callable[[str], RabbitMQClient]
) -> dict[str, mock.Mock]:
    # mock dask client
    dask_client_mock = mocker.patch("distributed.Client", autospec=True)

    # mock tasks get worker and state
    dask_distributed_worker_mock = mocker.patch(
        "simcore_service_dask_sidecar.utils.dask.get_worker", autospec=True
    )
    dask_task_mock = mocker.patch(
        "simcore_service_dask_sidecar.utils.dask.TaskState", autospec=True
    )
    dask_task_mock.resource_restrictions = {}
    dask_distributed_worker_mock.return_value.state.tasks.get.return_value = (
        dask_task_mock
    )

    # ensure dask logger propagates
    logging.getLogger("distributed").propagate = True

    # mock dask event worker
    dask_distributed_worker_events_mock = mocker.patch(
        "dask_task_models_library.container_tasks.events.get_worker", autospec=True
    )
    dask_distributed_worker_events_mock.return_value.get_current_task.return_value = (
        "pytest_jobid"
    )
    # mock dask event publishing
    mocker.patch(
        "simcore_service_dask_sidecar.utils.dask.is_current_task_aborted",
        autospec=True,
        return_value=False,
    )
    # mock dask rabbitmq plugin
    mock_dask_rabbitmq_plugin = mocker.patch(
        "simcore_service_dask_sidecar.rabbitmq_worker_plugin.RabbitMQPlugin",
        autospec=True,
    )
    mock_rabbitmq_client = create_rabbitmq_client("pytest_dask_sidecar_logs_publisher")
    mock_dask_rabbitmq_plugin.get_client.return_value = mock_rabbitmq_client
    mock_dask_rabbitmq_plugin.publish_message_from_any_thread = (
        mock_rabbitmq_client.publish
    )

    mocker.patch(
        "simcore_service_dask_sidecar.utils.dask.get_rabbitmq_client",
        autospec=True,
        return_value=mock_dask_rabbitmq_plugin,
    )

    return {
        "dask_client": dask_client_mock,
        "dask_task_state": dask_task_mock,
    }


@dataclass(slots=True, kw_only=True)
class ServiceExampleParam:
    docker_basic_auth: DockerBasicAuth
    service_key: str
    service_version: str
    command: list[str]
    input_data: TaskInputData
    output_data_keys: TaskOutputDataSchema
    log_file_url: AnyUrl
    expected_output_data: TaskOutputData
    expected_logs: list[str]
    integration_version: version.Version
    task_envs: dict[EnvVarKey, str]
    task_owner: TaskOwner
    boot_mode: BootMode
    s3_settings: S3Settings

    def sidecar_params(self) -> dict[str, Any]:
        return {
            "task_parameters": ContainerTaskParameters(
                image=self.service_key,
                tag=self.service_version,
                input_data=self.input_data,
                output_data_keys=self.output_data_keys,
                command=self.command,
                envs=self.task_envs,
                labels={},
                task_owner=self.task_owner,
                boot_mode=self.boot_mode,
            ),
            "docker_auth": self.docker_basic_auth,
            "log_file_url": self.log_file_url,
            "s3_settings": self.s3_settings,
        }


def _bash_check_env_exist(variable_name: str, variable_value: str) -> list[str]:
    return [
        f"if [ -z ${{{variable_name}+x}} ];then echo {variable_name} does not exist && exit 9;fi",
        f'if [ "${{{variable_name}}}" != "{variable_value}" ];then echo expected "{variable_value}" and found "${{{variable_name}}}" && exit 9;fi',
    ]


@pytest.fixture(
    params=list(BootMode),
    ids=lambda v: f"boot_mode.{v.name}",
)
def boot_mode(request: pytest.FixtureRequest) -> BootMode:
    return request.param


@pytest.fixture(
    # NOTE: legacy version comes second as it is less easy to debug issues with that one
    params=[
        "1.0.0",
        f"{LEGACY_INTEGRATION_VERSION}",
    ],
    ids=lambda v: f"integration.version.{v}",
)
def integration_version(request: pytest.FixtureRequest) -> version.Version:
    print("--> Using service integration:", request.param)
    return version.Version(request.param)


@pytest.fixture
def additional_envs(faker: Faker) -> dict[EnvVarKey, str]:
    return TypeAdapter(dict[EnvVarKey, str]).validate_python(
        faker.pydict(allowed_types=(str,))
    )


@pytest.fixture
def sleeper_task(
    integration_version: version.Version,
    file_on_s3_server: Callable[..., AnyUrl],
    s3_remote_file_url: Callable[..., AnyUrl],
    boot_mode: BootMode,
    additional_envs: dict[EnvVarKey, str],
    faker: Faker,
    task_owner: TaskOwner,
    s3_settings: S3Settings,
) -> ServiceExampleParam:
    """Creates a console task in an ubuntu distro that checks for the expected files and error in case they are missing"""
    # let's have some input files on the file server
    NUM_FILES = 12
    list_of_files = [file_on_s3_server() for _ in range(NUM_FILES)]

    # defines the inputs of the task
    input_data = TaskInputData.model_validate(
        {
            "input_1": 23,
            "input_23": "a string input",
            "the_input_43": 15.0,
            "the_bool_input_54": False,
            **{
                f"some_file_input_{index + 1}": FileUrl(url=file)
                for index, file in enumerate(list_of_files)
            },
            **{
                f"some_file_input_with_mapping{index + 1}": FileUrl(
                    url=file,
                    file_mapping=f"{index + 1}/some_file_input_{index + 1}",
                )
                for index, file in enumerate(list_of_files)
            },
        }
    )
    # check in the console that the expected files are present in the expected INPUT folder (set as ${INPUT_FOLDER} in the service)
    file_names = [file.path for file in list_of_files]
    list_of_bash_commands = [
        "echo User: $(id $(whoami))",
        "echo Inputs:",
        "ls -tlah -R ${INPUT_FOLDER}",
        "echo Outputs:",
        "ls -tlah -R ${OUTPUT_FOLDER}",
        "echo Logs:",
        "ls -tlah -R ${LOG_FOLDER}",
        "echo Envs:",
        "printenv",
    ]

    # check expected ENVS are set
    list_of_bash_commands += _bash_check_env_exist(
        variable_name="SC_COMP_SERVICES_SCHEDULED_AS",
        variable_value=f"{boot_mode.value}",
    )
    list_of_bash_commands += _bash_check_env_exist(
        variable_name="SIMCORE_NANO_CPUS_LIMIT",
        variable_value=f"{int(_DEFAULT_MAX_RESOURCES['CPU'] * 1e9)}",
    )
    list_of_bash_commands += _bash_check_env_exist(
        variable_name="SIMCORE_MEMORY_BYTES_LIMIT",
        variable_value=f"{_DEFAULT_MAX_RESOURCES['RAM']}",
    )
    for env_name, env_value in additional_envs.items():
        list_of_bash_commands += _bash_check_env_exist(
            variable_name=env_name, variable_value=env_value
        )

    # check input files
    list_of_bash_commands += [
        f"(test -f ${{INPUT_FOLDER}}/{file} || (echo ${{INPUT_FOLDER}}/{file} does not exist && exit 1))"
        for file in file_names
    ] + [f"echo $(cat ${{INPUT_FOLDER}}/{file})" for file in file_names]

    input_json_file_name = (
        "inputs.json"
        if integration_version > LEGACY_INTEGRATION_VERSION
        else "input.json"
    )

    list_of_bash_commands += [
        f"echo '{faker.text(max_nb_chars=17216)}'",
        f"(test -f ${{INPUT_FOLDER}}/{input_json_file_name} || (echo ${{INPUT_FOLDER}}/{input_json_file_name} file does not exists && exit 1))",
        f"echo $(cat ${{INPUT_FOLDER}}/{input_json_file_name})",
        f"sleep {randint(1, 4)}",  # noqa: S311
    ]

    # defines the expected outputs
    jsonable_outputs = {
        "pytest_string": "is quite an amazing feat",
        "pytest_integer": 432,
        "pytest_float": 3.2,
        "pytest_bool": False,
    }
    output_file_url = s3_remote_file_url(file_path="output_file")
    expected_output_keys = TaskOutputDataSchema.model_validate(
        {
            **(
                {k: {"required": True} for k in jsonable_outputs}
                | {
                    "pytest_file": {
                        "required": True,
                        "mapping": "a_outputfile",
                        "url": f"{output_file_url}",
                    },
                    "pytest_file_with_mapping": {
                        "required": True,
                        "mapping": "subfolder/a_outputfile",
                        "url": f"{output_file_url}",
                    },
                }
            ),
        }
    )
    expected_output_data = TaskOutputData.model_validate(
        {
            **(
                jsonable_outputs
                | {
                    "pytest_file": {
                        "url": f"{output_file_url}",
                        "file_mapping": "a_outputfile",
                    },
                    "pytest_file_with_mapping": {
                        "url": f"{output_file_url}",
                        "file_mapping": "subfolder/a_outputfile",
                    },
                }
            ),
        }
    )
    jsonized_outputs = json.dumps(jsonable_outputs).replace('"', '\\"')
    output_json_file_name = (
        "outputs.json"
        if integration_version > LEGACY_INTEGRATION_VERSION
        else "output.json"
    )

    # check for the log file if legacy version
    list_of_bash_commands += [
        "echo $(ls -tlah ${LOG_FOLDER})",
        f"(test {'!' if integration_version > LEGACY_INTEGRATION_VERSION else ''} -f ${{LOG_FOLDER}}/{LEGACY_SERVICE_LOG_FILE_NAME} || (echo ${{LOG_FOLDER}}/{LEGACY_SERVICE_LOG_FILE_NAME} file does {'' if integration_version > LEGACY_INTEGRATION_VERSION else 'not'} exists && exit 1))",
    ]
    if integration_version == LEGACY_INTEGRATION_VERSION:
        list_of_bash_commands = [
            f"{c} >> ${{LOG_FOLDER}}/{LEGACY_SERVICE_LOG_FILE_NAME}"
            for c in list_of_bash_commands
        ]
    # set the final command to generate the output file(s) (files and json output)
    list_of_bash_commands += [
        f"echo {jsonized_outputs} > ${{OUTPUT_FOLDER}}/{output_json_file_name}",
        "echo 'some data for the output file' > ${OUTPUT_FOLDER}/a_outputfile",
        "mkdir -p ${OUTPUT_FOLDER}/subfolder",
        "echo 'some data for the output file' > ${OUTPUT_FOLDER}/subfolder/a_outputfile",
    ]

    log_file_url = s3_remote_file_url(file_path="log.dat")

    return ServiceExampleParam(
        docker_basic_auth=DockerBasicAuth(
            server_address="docker.io", username="pytest", password=SecretStr("")
        ),
        #
        # NOTE: we use sleeper because it defines a user
        # that can write in outputs and the
        # sidecar can remove the outputs dirs
        # it is based on ubuntu though but the bad part is that now it uses sh instead of bash...
        # cause the entrypoint uses sh
        service_key="itisfoundation/sleeper",
        service_version="2.1.2",
        command=[
            "/bin/bash",
            "-c",
            " && ".join(list_of_bash_commands),
        ],
        input_data=input_data,
        output_data_keys=expected_output_keys,
        log_file_url=log_file_url,
        expected_output_data=expected_output_data,
        expected_logs=[
            json_dumps(
                {
                    "input_1": 23,
                    "input_23": "a string input",
                    "the_input_43": 15.0,
                    "the_bool_input_54": False,
                }
            ),
            "This is the file contents of file #'001'",
            "This is the file contents of file #'002'",
            "This is the file contents of file #'003'",
            "This is the file contents of file #'004'",
            "This is the file contents of file #'005'",
        ],
        integration_version=integration_version,
        task_envs=additional_envs,
        task_owner=task_owner,
        boot_mode=boot_mode,
        s3_settings=s3_settings,
    )


@pytest.fixture()
def sidecar_task(
    integration_version: version.Version,
    file_on_s3_server: Callable[..., AnyUrl],
    s3_remote_file_url: Callable[..., AnyUrl],
    boot_mode: BootMode,
    faker: Faker,
    task_owner: TaskOwner,
    s3_settings: S3Settings,
) -> Callable[..., ServiceExampleParam]:
    def _creator(
        command: list[str] | None = None, input_data: TaskInputData | None = None
    ) -> ServiceExampleParam:
        return ServiceExampleParam(
            docker_basic_auth=DockerBasicAuth(
                server_address="docker.io", username="pytest", password=SecretStr("")
            ),
            service_key="ubuntu",
            service_version="latest",
            command=command
            or ["/bin/bash", "-c", "echo 'hello I'm an empty ubuntu task!"],
            input_data=input_data or TaskInputData.model_validate({}),
            output_data_keys=TaskOutputDataSchema.model_validate({}),
            log_file_url=s3_remote_file_url(file_path="log.dat"),
            expected_output_data=TaskOutputData.model_validate({}),
            expected_logs=[],
            integration_version=integration_version,
            task_envs={},
            task_owner=task_owner,
            boot_mode=boot_mode,
            s3_settings=s3_settings,
        )

    return _creator


@pytest.fixture()
def failing_ubuntu_task(
    sidecar_task: Callable[..., ServiceExampleParam],
) -> ServiceExampleParam:
    return sidecar_task(command=["/bin/bash", "-c", "some stupid failing command"])


@pytest.fixture()
def sleeper_task_unexpected_output(
    sleeper_task: ServiceExampleParam,
) -> ServiceExampleParam:
    sleeper_task.command = ["/bin/bash", "-c", "echo we create nothingness"]
    return sleeper_task


@pytest.fixture()
def task_with_file_to_key_map_in_input_data(
    sidecar_task: Callable[..., ServiceExampleParam],
) -> ServiceExampleParam:
    """This task has a file-to-key map in the input data but receives zip data instead"""
    return sidecar_task(
        command=["/bin/bash", "-c", "echo we create nothingness"],
        input_data=TaskInputData.model_validate(
            {
                "input_1": 23,
                "input_23": "a string input",
                "the_input_43": 15.0,
                "the_bool_input_54": False,
                "some_file_input_with_mapping": FileUrl(
                    url=TypeAdapter(AnyUrl).validate_python(
                        "s3://myserver/some_file_url.zip"
                    ),
                    file_mapping="some_file_mapping",
                ),
            }
        ),
    )


@pytest.fixture()
def caplog_info_level(
    caplog: pytest.LogCaptureFixture,
) -> Iterable[pytest.LogCaptureFixture]:
    with caplog.at_level(logging.INFO, logger="simcore_service_dask_sidecar"):
        yield caplog


@pytest.fixture
def mocked_get_image_labels(
    integration_version: version.Version, mocker: MockerFixture
) -> mock.Mock:
    assert "json_schema_extra" in ServiceMetaDataPublished.model_config
    labels: ImageLabels = TypeAdapter(ImageLabels).validate_python(
        ServiceMetaDataPublished.model_json_schema()["examples"][0],
    )
    labels.integration_version = f"{integration_version}"
    return mocker.patch(
        "simcore_service_dask_sidecar.computational_sidecar.core.get_image_labels",
        autospec=True,
        return_value=labels,
    )


@pytest.fixture
async def log_rabbit_client_parser(
    create_rabbitmq_client: Callable[[str], RabbitMQClient], mocker: MockerFixture
) -> AsyncIterator[mock.AsyncMock]:
    # Create a threading event to track when subscription is ready
    ready_event = threading.Event()
    shutdown_event = threading.Event()
    the_mock = mocker.AsyncMock(return_value=True)

    # Worker function to process messages in a separate thread
    def message_processor(a_mock: mock.AsyncMock):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        client = create_rabbitmq_client("dask_sidecar_pytest_logs_consumer")

        async def subscribe_and_process(a_mock: mock.AsyncMock):
            queue_name, _ = await client.subscribe(
                LoggerRabbitMessage.get_channel_name(),
                a_mock,
                exclusive_queue=False,
                topics=[BIND_TO_ALL_TOPICS],
            )
            ready_event.set()

            # Wait until the test is done
            while not shutdown_event.is_set():  # noqa: ASYNC110
                await asyncio.sleep(0.1)

            # Cleanup
            await client.unsubscribe(queue_name)

        loop.run_until_complete(subscribe_and_process(a_mock))
        loop.run_until_complete(client.close())
        loop.close()

    # Start the worker thread
    worker = threading.Thread(
        target=message_processor, kwargs={"a_mock": the_mock}, daemon=False
    )
    worker.start()

    # Wait for subscription to be ready
    assert ready_event.wait(timeout=10), "Failed to initialize RabbitMQ subscription"

    try:
        yield the_mock
    finally:
        # Signal the worker thread to shut down
        shutdown_event.set()
        worker.join(timeout=5)
        if worker.is_alive():
            _logger.warning("RabbitMQ worker thread did not terminate properly")


def test_run_computational_sidecar_real_fct(
    caplog_info_level: pytest.LogCaptureFixture,
    app_environment: EnvVarsDict,
    dask_subsystem_mock: dict[str, mock.Mock],
    sleeper_task: ServiceExampleParam,
    mocked_get_image_labels: mock.Mock,
    s3_settings: S3Settings,
    log_rabbit_client_parser: mock.AsyncMock,
):
    output_data = run_computational_sidecar(
        **sleeper_task.sidecar_params(),
    )
    mocked_get_image_labels.assert_called_once_with(
        mock.ANY,
        sleeper_task.docker_basic_auth,
        sleeper_task.service_key,
        sleeper_task.service_version,
    )
    assert log_rabbit_client_parser.called

    # check that the task produces expected logs
    for log in sleeper_task.expected_logs:
        r = re.compile(
            rf"\[{sleeper_task.service_key}:{sleeper_task.service_version} - .+\/.+\]: ({log})"
        )
        search_results = list(filter(r.search, caplog_info_level.messages))
        assert (
            len(search_results) > 0
        ), f"Could not find '{log}' in worker_logs:\n {pformat(caplog_info_level.messages, width=240)}"
    for log in sleeper_task.expected_logs:
        assert re.search(
            rf"\[{sleeper_task.service_key}:{sleeper_task.service_version} - .+\/.+\]: ({log})",
            caplog_info_level.text,
        )
    # check that the task produce the expected data, not less not more
    for k, v in sleeper_task.expected_output_data.items():
        assert k in output_data
        assert output_data[k] == v

    s3_storage_kwargs = _s3fs_settings_from_s3_settings(s3_settings)

    for k, v in output_data.items():
        assert k in sleeper_task.expected_output_data
        assert v == sleeper_task.expected_output_data[k]

        # if there are file urls in the output, check they exist
        if isinstance(v, FileUrl):
            with fsspec.open(f"{v.url}", **s3_storage_kwargs) as fp:
                assert fp.details.get("size") > 0  # type: ignore

    # check the task has created a log file
    with fsspec.open(
        f"{sleeper_task.log_file_url}", mode="rt", **s3_storage_kwargs
    ) as fp:
        saved_logs = fp.read()  # type: ignore
    assert saved_logs
    for log in sleeper_task.expected_logs:
        assert log in saved_logs


@pytest.mark.parametrize(
    "integration_version, boot_mode", [("1.0.0", BootMode.CPU)], indirect=True
)
def test_run_multiple_computational_sidecar_dask(
    dask_client: distributed.Client,
    sleeper_task: ServiceExampleParam,
    mocked_get_image_labels: mock.Mock,
):
    NUMBER_OF_TASKS = 50

    futures = [
        dask_client.submit(
            run_computational_sidecar,
            **sleeper_task.sidecar_params(),
            resources={},
        )
        for _ in range(NUMBER_OF_TASKS)
    ]

    results = dask_client.gather(futures)
    assert results
    assert isinstance(results, list)
    # for result in results:
    # check that the task produce the expected data, not less not more
    for output_data in results:
        for k, v in sleeper_task.expected_output_data.items():
            assert k in output_data
            assert output_data[k] == v

    mocked_get_image_labels.assert_called()


@pytest.fixture
def progress_event_handler(dask_client: distributed.Client) -> mock.Mock:
    mocked_parser = mock.Mock()
    dask_client.subscribe_topic(TaskProgressEvent.topic_name(), mocked_parser)
    return mocked_parser


def _assert_parse_progresses_from_progress_event_handler(
    progress_event_handler: mock.Mock,
) -> list[float]:
    assert progress_event_handler.called
    worker_progresses = [
        TaskProgressEvent.model_validate_json(msg.args[0][1]).progress
        for msg in progress_event_handler.call_args_list
    ]
    assert worker_progresses == sorted(
        set(worker_progresses)
    ), "ordering of progress values incorrectly sorted!"
    assert worker_progresses[0] == 0, "missing/incorrect initial progress value"
    assert worker_progresses[-1] == 1, "missing/incorrect final progress value"
    return worker_progresses


@pytest.mark.parametrize(
    "integration_version, boot_mode", [("1.0.0", BootMode.CPU)], indirect=True
)
async def test_run_computational_sidecar_dask(
    app_environment: EnvVarsDict,
    sleeper_task: ServiceExampleParam,
    progress_event_handler: mock.Mock,
    mocked_get_image_labels: mock.Mock,
    s3_settings: S3Settings,
    log_rabbit_client_parser: mock.AsyncMock,
    dask_client: distributed.Client,
):
    future = dask_client.submit(
        run_computational_sidecar,
        **sleeper_task.sidecar_params(),
        resources={},
    )

    worker_name = next(iter(dask_client.scheduler_info()["workers"]))
    assert worker_name
    output_data = future.result()
    assert output_data
    assert isinstance(output_data, TaskOutputData)

    # check that the task produces expected logs
    _assert_parse_progresses_from_progress_event_handler(progress_event_handler)

    async for attempt in AsyncRetrying(
        wait=wait_fixed(1),
        stop=stop_after_delay(30),
        reraise=True,
        retry=retry_if_exception_type(AssertionError),
    ):
        with attempt:
            assert log_rabbit_client_parser.called
            worker_logs = [
                message
                for msg in log_rabbit_client_parser.call_args_list
                for message in LoggerRabbitMessage.model_validate_json(
                    msg.args[0]
                ).messages
            ]

            print(f"<-- we got {len(worker_logs)} lines of logs")

            for log in sleeper_task.expected_logs:
                r = re.compile(rf"^({log}).*")
                search_results = list(filter(r.search, worker_logs))
                assert (
                    len(search_results) > 0
                ), f"Could not find {log} in worker_logs:\n {pformat(worker_logs, width=240)}"

    # check that the task produce the expected data, not less not more
    assert isinstance(output_data, TaskOutputData)
    for k, v in sleeper_task.expected_output_data.items():
        assert k in output_data
        assert output_data[k] == v

    s3_storage_kwargs = _s3fs_settings_from_s3_settings(s3_settings)
    for k, v in output_data.items():
        assert k in sleeper_task.expected_output_data
        assert v == sleeper_task.expected_output_data[k]

        # if there are file urls in the output, check they exist
        if isinstance(v, FileUrl):
            with fsspec.open(f"{v.url}", **s3_storage_kwargs) as fp:
                assert fp.details.get("size") > 0  # type: ignore
    mocked_get_image_labels.assert_called()


@pytest.mark.parametrize(
    "integration_version, boot_mode, task_owner",
    [("1.0.0", BootMode.CPU, "no_parent_node")],
    indirect=True,
)
async def test_run_computational_sidecar_dask_does_not_lose_messages_with_pubsub(
    dask_client: distributed.Client,
    sidecar_task: Callable[..., ServiceExampleParam],
    progress_event_handler: mock.Mock,
    mocked_get_image_labels: mock.Mock,
    log_rabbit_client_parser: mock.AsyncMock,
):
    mocked_get_image_labels.assert_not_called()
    NUMBER_OF_LOGS = 20000
    future = dask_client.submit(
        run_computational_sidecar,
        **sidecar_task(
            command=[
                "/bin/bash",
                "-c",
                " && ".join(
                    [
                        f'N={NUMBER_OF_LOGS}; for ((i=1; i<=N; i++));do echo "This is iteration $i"; echo "progress: $i/{NUMBER_OF_LOGS}"; done '
                    ]
                ),
            ],
        ).sidecar_params(),
        resources={},
    )
    output_data = future.result()
    assert output_data is not None
    assert isinstance(output_data, TaskOutputData)

    # check that the task produces expected logs
    _assert_parse_progresses_from_progress_event_handler(progress_event_handler)

    async for attempt in AsyncRetrying(
        wait=wait_fixed(1),
        stop=stop_after_delay(30),
        reraise=True,
        retry=retry_if_exception_type(AssertionError),
    ):
        with attempt:
            assert log_rabbit_client_parser.called

            worker_logs = [
                message
                for msg in log_rabbit_client_parser.call_args_list
                for message in LoggerRabbitMessage.model_validate_json(
                    msg.args[0]
                ).messages
            ]
            # check all the awaited logs are in there
            filtered_worker_logs = filter(
                lambda log: "This is iteration" in log, worker_logs
            )
            assert len(list(filtered_worker_logs)) == NUMBER_OF_LOGS
    mocked_get_image_labels.assert_called()


@pytest.mark.parametrize(
    "integration_version, boot_mode", [("1.0.0", BootMode.CPU)], indirect=True
)
def test_failing_service_raises_exception(
    caplog_info_level: pytest.LogCaptureFixture,
    app_environment: EnvVarsDict,
    dask_subsystem_mock: dict[str, mock.Mock],
    failing_ubuntu_task: ServiceExampleParam,
    mocked_get_image_labels: mock.Mock,
):
    with pytest.raises(ServiceRuntimeError):
        run_computational_sidecar(**failing_ubuntu_task.sidecar_params())


@pytest.mark.parametrize(
    "integration_version, boot_mode", [("1.0.0", BootMode.CPU)], indirect=True
)
def test_running_service_that_generates_unexpected_data_raises_exception(
    caplog_info_level: pytest.LogCaptureFixture,
    app_environment: EnvVarsDict,
    dask_subsystem_mock: dict[str, mock.Mock],
    sleeper_task_unexpected_output: ServiceExampleParam,
):
    with pytest.raises(ServiceBadFormattedOutputError):
        run_computational_sidecar(
            **sleeper_task_unexpected_output.sidecar_params(),
        )


@pytest.mark.parametrize(
    "integration_version, boot_mode", [("1.0.0", BootMode.CPU)], indirect=True
)
def test_running_service_with_incorrect_zip_data_that_uses_a_file_to_key_map_raises_exception(
    caplog_info_level: pytest.LogCaptureFixture,
    app_environment: EnvVarsDict,
    dask_subsystem_mock: dict[str, mock.Mock],
    task_with_file_to_key_map_in_input_data: ServiceExampleParam,
):
    with pytest.raises(ServiceInputsUseFileToKeyMapButReceivesZipDataError):
        run_computational_sidecar(
            **task_with_file_to_key_map_in_input_data.sidecar_params(),
        )


@pytest.mark.parametrize(
    "integration_version, boot_mode", [("1.0.0", BootMode.CPU)], indirect=True
)
def test_delayed_logging_with_small_timeout_raises_exception(
    caplog: pytest.LogCaptureFixture,
    app_environment: EnvVarsDict,
    dask_subsystem_mock: dict[str, mock.Mock],
    sidecar_task: Callable[..., ServiceExampleParam],
    mocked_get_image_labels: mock.Mock,
    mocker: MockerFixture,
):
    """https://github.com/aio-libs/aiodocker/issues/901"""
    # Mock the timeout with a very small value
    mocker.patch(
        "simcore_service_dask_sidecar.computational_sidecar.docker_utils._AIODOCKER_LOGS_TIMEOUT_S",
        0.5,  # Small timeout that should cause failure
    )

    # Configure the task to sleep first and then generate logs
    waiting_task = sidecar_task(
        command=[
            "/bin/bash",
            "-c",
            'echo "Starting task"; sleep 5; echo "After sleep"',
        ]
    )

    # Execute the task and expect a timeout exception in the logs
    with caplog.at_level(logging.ERROR, logger="simcore_service_dask_sidecar"):
        run_computational_sidecar(**waiting_task.sidecar_params())
        assert len(caplog.records) == 1
        record = caplog.records[0]
        assert record.exc_info
        assert isinstance(record.exc_info[1], TimeoutError)
    caplog.clear()
    mocker.patch(
        "simcore_service_dask_sidecar.computational_sidecar.docker_utils._AIODOCKER_LOGS_TIMEOUT_S",
        10,  # larger timeout to avoid issues
    )
    with caplog.at_level(logging.ERROR, logger="simcore_service_dask_sidecar"):
        run_computational_sidecar(**waiting_task.sidecar_params())
        assert len(caplog.records) == 0
