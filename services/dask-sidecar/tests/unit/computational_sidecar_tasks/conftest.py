# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=no-member
# pylint: disable=too-many-instance-attributes

import asyncio
import datetime
import json
import logging
import threading
from collections.abc import AsyncIterator, Callable, Iterable
from random import randint
from unittest import mock

import distributed
import pytest
from common_library.json_serialization import json_dumps
from dask_task_models_library.container_tasks.docker import DockerBasicAuth
from dask_task_models_library.container_tasks.events import TaskProgressEvent
from dask_task_models_library.container_tasks.io import (
    FileUrl,
    TaskInputData,
    TaskOutputData,
    TaskOutputDataSchema,
)
from dask_task_models_library.container_tasks.protocol import TaskOwner
from faker import Faker
from models_library.basic_types import EnvVarKey
from models_library.rabbitmq_messages import LoggerRabbitMessage
from models_library.services import ServiceMetaDataPublished
from models_library.services_resources import BootMode
from packaging import version
from pydantic import AnyUrl, SecretStr, TypeAdapter
from pytest_mock.plugin import MockerFixture
from pytest_simcore.helpers.dask_sidecar_tasks import ServiceExampleParam
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from servicelib.rabbitmq._client import RabbitMQClient
from servicelib.rabbitmq._constants import BIND_TO_ALL_TOPICS
from settings_library.s3 import S3Settings
from simcore_service_dask_sidecar.computational_sidecar.docker_utils import (
    LEGACY_SERVICE_LOG_FILE_NAME,
)
from simcore_service_dask_sidecar.computational_sidecar.models import (
    LEGACY_INTEGRATION_VERSION,
    ImageLabels,
)
from simcore_service_dask_sidecar.utils.dask import _DEFAULT_MAX_RESOURCES

_logger = logging.getLogger(__name__)


@pytest.fixture()
def dask_subsystem_mock(
    mocker: MockerFixture, create_rabbitmq_client: Callable[[str], RabbitMQClient]
) -> dict[str, mock.Mock]:
    # mock dask client
    dask_client_mock = mocker.patch("distributed.Client", autospec=True)

    # mock tasks get worker and state
    dask_distributed_worker_mock = mocker.patch("simcore_service_dask_sidecar.utils.dask.get_worker", autospec=True)
    dask_task_mock = mocker.patch("simcore_service_dask_sidecar.utils.dask.TaskState", autospec=True)
    dask_task_mock.resource_restrictions = {}
    dask_distributed_worker_mock.return_value.state.tasks.get.return_value = dask_task_mock

    # ensure dask logger propagates
    logging.getLogger("distributed").propagate = True

    # mock dask event worker
    dask_distributed_worker_events_mock = mocker.patch(
        "dask_task_models_library.container_tasks.events.get_worker", autospec=True
    )
    dask_distributed_worker_events_mock.return_value.get_current_task.return_value = "pytest_jobid"
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
    mock_dask_rabbitmq_plugin.publish_message_from_any_thread = mock_rabbitmq_client.publish

    mocker.patch(
        "simcore_service_dask_sidecar.utils.dask.get_rabbitmq_client",
        autospec=True,
        return_value=mock_dask_rabbitmq_plugin,
    )

    return {
        "dask_client": dask_client_mock,
        "dask_task_state": dask_task_mock,
    }


def _bash_check_env_exist(variable_name: str, variable_value: str) -> list[str]:
    return [
        f"if [ -z ${{{variable_name}+x}} ];then echo {variable_name} does not exist && exit 9;fi",
        f'if [ "${{{variable_name}}}" != "{variable_value}" ];then echo expected '
        f'"{variable_value}" and found "${{{variable_name}}}" && exit 9;fi',
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
    return TypeAdapter(dict[EnvVarKey, str]).validate_python(faker.pydict(allowed_types=(str,)))


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
    """Creates a console task in an ubuntu distro that
    checks for the expected files and error in case they are missing"""
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
            **{f"some_file_input_{index + 1}": FileUrl(url=file) for index, file in enumerate(list_of_files)},
            **{
                f"some_file_input_with_mapping{index + 1}": FileUrl(
                    url=file,
                    file_mapping=f"{index + 1}/some_file_input_{index + 1}",
                )
                for index, file in enumerate(list_of_files)
            },
        }
    )
    # check in the console that the expected files are present
    # in the expected INPUT folder (set as ${INPUT_FOLDER} in the service)
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
        list_of_bash_commands += _bash_check_env_exist(variable_name=env_name, variable_value=env_value)

    # check input files
    list_of_bash_commands += [
        f"(test -f ${{INPUT_FOLDER}}/{file} || (echo ${{INPUT_FOLDER}}/{file} does not exist && exit 1))"
        for file in file_names
    ] + [f"echo $(cat ${{INPUT_FOLDER}}/{file})" for file in file_names]

    input_json_file_name = "inputs.json" if integration_version > LEGACY_INTEGRATION_VERSION else "input.json"

    list_of_bash_commands += [
        f"echo '{faker.text(max_nb_chars=17216)}'",
        f"(test -f ${{INPUT_FOLDER}}/{input_json_file_name} || "
        f"(echo ${{INPUT_FOLDER}}/{input_json_file_name} file does not exists && exit 1))",
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
    output_json_file_name = "outputs.json" if integration_version > LEGACY_INTEGRATION_VERSION else "output.json"

    # check for the log file if legacy version
    list_of_bash_commands += [
        "echo $(ls -tlah ${LOG_FOLDER})",
        f"(test {'!' if integration_version > LEGACY_INTEGRATION_VERSION else ''} "
        f"-f ${{LOG_FOLDER}}/{LEGACY_SERVICE_LOG_FILE_NAME} || "
        f"(echo ${{LOG_FOLDER}}/{LEGACY_SERVICE_LOG_FILE_NAME} file does "
        f"{'' if integration_version > LEGACY_INTEGRATION_VERSION else 'not'} exists && exit 1))",
    ]
    if integration_version == LEGACY_INTEGRATION_VERSION:
        list_of_bash_commands = [
            f"{c} >> ${{LOG_FOLDER}}/{LEGACY_SERVICE_LOG_FILE_NAME}" for c in list_of_bash_commands
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
        docker_basic_auth=DockerBasicAuth(server_address="docker.io", username="pytest", password=SecretStr("")),
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
        service_key: str | None = None,
        service_version: str | None = None,
        command: list[str] | None = None,
        input_data: TaskInputData | None = None,
    ) -> ServiceExampleParam:
        return ServiceExampleParam(
            docker_basic_auth=DockerBasicAuth(server_address="docker.io", username="pytest", password=SecretStr("")),
            service_key=service_key or "ubuntu",
            service_version=service_version or "latest",
            command=command or ["/bin/bash", "-c", "echo 'hello I'm an empty ubuntu task!"],
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
                    url=TypeAdapter(AnyUrl).validate_python("s3://myserver/some_file_url.zip"),
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
def mocked_get_image_labels(integration_version: version.Version, mocker: MockerFixture) -> mock.Mock:
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
    worker = threading.Thread(target=message_processor, kwargs={"a_mock": the_mock}, daemon=False)
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


@pytest.fixture
def progress_event_handler(dask_client: distributed.Client) -> mock.Mock:
    mocked_parser = mock.Mock()
    dask_client.subscribe_topic(TaskProgressEvent.topic_name(), mocked_parser)
    return mocked_parser


@pytest.fixture
def with_short_max_silence_timeout(
    app_environment: EnvVarsDict,
    monkeypatch: pytest.MonkeyPatch,
) -> EnvVarsDict:
    return app_environment | setenvs_from_dict(
        monkeypatch,
        {
            "DASK_SIDECAR_MAX_LOG_SILENCE_TIMEOUT": f"{datetime.timedelta(seconds=0.5)}",
        },
    )
