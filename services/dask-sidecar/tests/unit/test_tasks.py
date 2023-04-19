# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=no-member
# pylint: disable=too-many-instance-attributes

import asyncio
import json
import logging
import re

# copied out from dask
from dataclasses import dataclass
from pprint import pformat
from random import randint
from typing import Callable, Coroutine, Iterable
from unittest import mock
from uuid import uuid4

import fsspec
import pytest
from dask_task_models_library.container_tasks.docker import DockerBasicAuth
from dask_task_models_library.container_tasks.errors import ServiceRuntimeError
from dask_task_models_library.container_tasks.events import (
    TaskLogEvent,
    TaskProgressEvent,
)
from dask_task_models_library.container_tasks.io import (
    FileUrl,
    TaskInputData,
    TaskOutputData,
    TaskOutputDataSchema,
)
from distributed import Client
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.services_resources import BootMode
from models_library.users import UserID
from packaging import version
from pydantic import AnyUrl, SecretStr
from pytest import FixtureRequest, LogCaptureFixture
from pytest_mock.plugin import MockerFixture
from settings_library.s3 import S3Settings
from simcore_service_dask_sidecar.computational_sidecar.docker_utils import (
    LEGACY_SERVICE_LOG_FILE_NAME,
)
from simcore_service_dask_sidecar.computational_sidecar.errors import (
    ServiceBadFormattedOutputError,
)
from simcore_service_dask_sidecar.computational_sidecar.models import (
    LEGACY_INTEGRATION_VERSION,
)
from simcore_service_dask_sidecar.dask_utils import _DEFAULT_MAX_RESOURCES
from simcore_service_dask_sidecar.file_utils import _s3fs_settings_from_s3_settings
from simcore_service_dask_sidecar.tasks import run_computational_sidecar

logger = logging.getLogger(__name__)


@pytest.fixture
def job_id() -> str:
    return "some_incredible_string"


@pytest.fixture
def user_id() -> UserID:
    return 1


@pytest.fixture
def project_id() -> ProjectID:
    return uuid4()


@pytest.fixture
def node_id() -> NodeID:
    return uuid4()


@pytest.fixture()
def dask_subsystem_mock(mocker: MockerFixture) -> dict[str, MockerFixture]:
    # mock dask client
    dask_client_mock = mocker.patch("distributed.Client", autospec=True)

    # mock tasks get worker and state
    dask_distributed_worker_mock = mocker.patch(
        "simcore_service_dask_sidecar.dask_utils.get_worker", autospec=True
    )
    dask_task_mock = mocker.patch(
        "simcore_service_dask_sidecar.dask_utils.TaskState", autospec=True
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
    dask_utils_publish_event_mock = mocker.patch(
        "simcore_service_dask_sidecar.dask_utils.distributed.Pub",
        autospec=True,
    )
    mocker.patch(
        "simcore_service_dask_sidecar.dask_utils.distributed.Sub",
        autospec=True,
    )
    mocker.patch(
        "simcore_service_dask_sidecar.dask_utils.is_current_task_aborted",
        autospec=True,
        return_value=False,
    )

    return {
        "dask_client": dask_client_mock,
        "dask_task_state": dask_task_mock,
        "dask_event_publish": dask_utils_publish_event_mock,
    }


@dataclass
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


pytest_simcore_core_services_selection = ["postgres"]
pytest_simcore_ops_services_selection = ["minio"]


def _bash_check_env_exist(variable_name: str, variable_value: str) -> list[str]:
    return [
        f"if [ -z ${{{variable_name}+x}} ];then echo {variable_name} does not exist && exit 9;fi",
        f'if [ "${{{variable_name}}}" != "{variable_value}" ];then echo expected "{variable_value}" and found "${{{variable_name}}}" && exit 9;fi',
    ]


@pytest.fixture(params=list(BootMode), ids=str)
def boot_mode(request: FixtureRequest) -> BootMode:
    return request.param


@pytest.fixture(
    # NOTE: legacy version comes second as it is less easy to debug issues with that one
    params=[
        "1.0.0",
        f"{LEGACY_INTEGRATION_VERSION}",
    ],
    ids=lambda v: f"integration.version.{v}",
)
def integration_version(request: FixtureRequest) -> version.Version:
    print("Using service integration:", request.param)
    return version.Version(request.param)


@pytest.fixture
def ubuntu_task(
    integration_version: version.Version,
    file_on_s3_server: Callable[..., AnyUrl],
    s3_remote_file_url: Callable[..., AnyUrl],
    boot_mode: BootMode,
) -> ServiceExampleParam:
    """Creates a console task in an ubuntu distro that checks for the expected files and error in case they are missing"""
    # let's have some input files on the file server
    NUM_FILES = 12
    list_of_files = [file_on_s3_server() for _ in range(NUM_FILES)]

    # defines the inputs of the task
    input_data = TaskInputData.parse_obj(
        {
            "input_1": 23,
            "input_23": "a string input",
            "the_input_43": 15.0,
            "the_bool_input_54": False,
            **{
                f"some_file_input_{index+1}": FileUrl(url=file)
                for index, file in enumerate(list_of_files)
            },
            **{
                f"some_file_input_with_mapping{index+1}": FileUrl(
                    url=file,
                    file_mapping=f"{index+1}/some_file_input_{index+1}",
                )
                for index, file in enumerate(list_of_files)
            },
        }
    )
    # check in the console that the expected files are present in the expected INPUT folder (set as ${INPUT_FOLDER} in the service)
    file_names = [file.path for file in list_of_files]
    list_of_commands = [
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
    list_of_commands += _bash_check_env_exist(
        variable_name="SC_COMP_SERVICES_SCHEDULED_AS", variable_value=boot_mode.value
    )
    list_of_commands += _bash_check_env_exist(
        variable_name="SIMCORE_NANO_CPUS_LIMIT",
        variable_value=f"{int(_DEFAULT_MAX_RESOURCES['CPU']*1e9)}",
    )
    list_of_commands += _bash_check_env_exist(
        variable_name="SIMCORE_MEMORY_BYTES_LIMIT",
        variable_value=f"{_DEFAULT_MAX_RESOURCES['RAM']}",
    )

    # check input files
    list_of_commands += [
        f"(test -f ${{INPUT_FOLDER}}/{file} || (echo ${{INPUT_FOLDER}}/{file} does not exist && exit 1))"
        for file in file_names
    ] + [f"echo $(cat ${{INPUT_FOLDER}}/{file})" for file in file_names]

    input_json_file_name = (
        "inputs.json"
        if integration_version > LEGACY_INTEGRATION_VERSION
        else "input.json"
    )

    list_of_commands += [
        f"(test -f ${{INPUT_FOLDER}}/{input_json_file_name} || (echo ${{INPUT_FOLDER}}/{input_json_file_name} file does not exists && exit 1))",
        f"echo $(cat ${{INPUT_FOLDER}}/{input_json_file_name})",
        f"sleep {randint(1,4)}",
    ]

    # defines the expected outputs
    jsonable_outputs = {
        "pytest_string": "is quite an amazing feat",
        "pytest_integer": 432,
        "pytest_float": 3.2,
        "pytest_bool": False,
    }
    output_file_url = s3_remote_file_url(file_path="output_file")
    expected_output_keys = TaskOutputDataSchema.parse_obj(
        {
            **{k: {"required": True} for k in jsonable_outputs.keys()},
            **{
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
            },
        }
    )
    expected_output_data = TaskOutputData.parse_obj(
        {
            **jsonable_outputs,
            **{
                "pytest_file": {
                    "url": f"{output_file_url}",
                    "file_mapping": "a_outputfile",
                },
                "pytest_file_with_mapping": {
                    "url": f"{output_file_url}",
                    "file_mapping": "subfolder/a_outputfile",
                },
            },
        }
    )
    jsonized_outputs = json.dumps(jsonable_outputs).replace('"', '\\"')
    output_json_file_name = (
        "outputs.json"
        if integration_version > LEGACY_INTEGRATION_VERSION
        else "output.json"
    )

    # check for the log file if legacy version
    list_of_commands += [
        "echo $(ls -tlah ${LOG_FOLDER})",
        f"(test {'!' if integration_version > LEGACY_INTEGRATION_VERSION else ''} -f ${{LOG_FOLDER}}/{LEGACY_SERVICE_LOG_FILE_NAME} || (echo ${{LOG_FOLDER}}/{LEGACY_SERVICE_LOG_FILE_NAME} file does {'' if integration_version > LEGACY_INTEGRATION_VERSION else 'not'} exists && exit 1))",
    ]
    if integration_version == LEGACY_INTEGRATION_VERSION:
        list_of_commands = [
            f"{c} >> ${{LOG_FOLDER}}/{LEGACY_SERVICE_LOG_FILE_NAME}"
            for c in list_of_commands
        ]
    # set the final command to generate the output file(s) (files and json output)
    list_of_commands += [
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
            " && ".join(list_of_commands),
        ],
        input_data=input_data,
        output_data_keys=expected_output_keys,
        log_file_url=log_file_url,
        expected_output_data=expected_output_data,
        expected_logs=[
            '{"input_1": 23, "input_23": "a string input", "the_input_43": 15.0, "the_bool_input_54": false}',
            "This is the file contents of file #'001'",
            "This is the file contents of file #'002'",
            "This is the file contents of file #'003'",
            "This is the file contents of file #'004'",
            "This is the file contents of file #'005'",
        ],
        integration_version=integration_version,
    )


@pytest.fixture()
def ubuntu_task_fail(ubuntu_task: ServiceExampleParam) -> ServiceExampleParam:
    ubuntu_task.command = ["/bin/bash", "-c", "some stupid failing command"]
    return ubuntu_task


@pytest.fixture()
def ubuntu_task_unexpected_output(
    ubuntu_task: ServiceExampleParam,
) -> ServiceExampleParam:
    ubuntu_task.command = ["/bin/bash", "-c", "echo we create nothingness"]
    return ubuntu_task


@pytest.fixture()
def caplog_info_level(caplog: LogCaptureFixture) -> Iterable[LogCaptureFixture]:
    with caplog.at_level(
        logging.INFO,
    ):
        yield caplog


def test_run_computational_sidecar_real_fct(
    caplog_info_level: LogCaptureFixture,
    event_loop: asyncio.AbstractEventLoop,
    mock_service_envs: None,
    dask_subsystem_mock: dict[str, MockerFixture],
    ubuntu_task: ServiceExampleParam,
    mocker: MockerFixture,
    s3_settings: S3Settings,
    boot_mode: BootMode,
):
    mocked_get_integration_version = mocker.patch(
        "simcore_service_dask_sidecar.computational_sidecar.core.get_integration_version",
        autospec=True,
        return_value=ubuntu_task.integration_version,
    )
    output_data = run_computational_sidecar(
        ubuntu_task.docker_basic_auth,
        ubuntu_task.service_key,
        ubuntu_task.service_version,
        ubuntu_task.input_data,
        ubuntu_task.output_data_keys,
        ubuntu_task.log_file_url,
        ubuntu_task.command,
        s3_settings,
        boot_mode,
    )
    mocked_get_integration_version.assert_called_once_with(
        mock.ANY,
        ubuntu_task.docker_basic_auth,
        ubuntu_task.service_key,
        ubuntu_task.service_version,
    )
    for event in [TaskProgressEvent, TaskLogEvent]:
        dask_subsystem_mock["dask_event_publish"].assert_any_call(  # type: ignore
            name=event.topic_name()
        )

    # check that the task produces expected logs
    for log in ubuntu_task.expected_logs:
        r = re.compile(
            rf"\[{ubuntu_task.service_key}:{ubuntu_task.service_version} - .+\/.+ - .+\]: ({log})"
        )
        search_results = list(filter(r.search, caplog_info_level.messages))
        assert (
            len(search_results) > 0
        ), f"Could not find '{log}' in worker_logs:\n {pformat(caplog_info_level.messages, width=240)}"
    for log in ubuntu_task.expected_logs:
        assert re.search(
            rf"\[{ubuntu_task.service_key}:{ubuntu_task.service_version} - .+\/.+ - .+\]: ({log})",
            caplog_info_level.text,
        )
    # check that the task produce the expected data, not less not more
    for k, v in ubuntu_task.expected_output_data.items():
        assert k in output_data
        assert output_data[k] == v

    s3_storage_kwargs = _s3fs_settings_from_s3_settings(s3_settings)

    for k, v in output_data.items():
        assert k in ubuntu_task.expected_output_data
        assert v == ubuntu_task.expected_output_data[k]

        # if there are file urls in the output, check they exist
        if isinstance(v, FileUrl):
            with fsspec.open(f"{v.url}", **s3_storage_kwargs) as fp:
                assert fp.details.get("size") > 0  # type: ignore

    # check the task has created a log file
    with fsspec.open(
        f"{ubuntu_task.log_file_url}", mode="rt", **s3_storage_kwargs
    ) as fp:
        saved_logs = fp.read()  # type: ignore
    assert saved_logs
    for log in ubuntu_task.expected_logs:
        assert log in saved_logs


@pytest.mark.parametrize(
    "integration_version, boot_mode", [("1.0.0", BootMode.CPU)], indirect=True
)
def test_run_multiple_computational_sidecar_dask(
    event_loop: asyncio.AbstractEventLoop,
    dask_client: Client,
    ubuntu_task: ServiceExampleParam,
    mocker: MockerFixture,
    s3_settings: S3Settings,
    boot_mode: BootMode,
):
    NUMBER_OF_TASKS = 50

    mocker.patch(
        "simcore_service_dask_sidecar.computational_sidecar.core.get_integration_version",
        autospec=True,
        return_value=ubuntu_task.integration_version,
    )
    futures = [
        dask_client.submit(
            run_computational_sidecar,
            ubuntu_task.docker_basic_auth,
            ubuntu_task.service_key,
            ubuntu_task.service_version,
            ubuntu_task.input_data,
            ubuntu_task.output_data_keys,
            ubuntu_task.log_file_url,
            ubuntu_task.command,
            s3_settings,
            resources={},
            boot_mode=boot_mode,
        )
        for _ in range(NUMBER_OF_TASKS)
    ]

    results = dask_client.gather(futures)
    assert results
    assert not isinstance(results, Coroutine)
    # for result in results:
    # check that the task produce the expected data, not less not more
    for output_data in results:
        for k, v in ubuntu_task.expected_output_data.items():
            assert k in output_data
            assert output_data[k] == v


@pytest.mark.parametrize(
    "integration_version, boot_mode", [("1.0.0", BootMode.CPU)], indirect=True
)
def test_run_computational_sidecar_dask(
    dask_client: Client,
    ubuntu_task: ServiceExampleParam,
    mocker: MockerFixture,
    s3_settings: S3Settings,
    boot_mode: BootMode,
):
    mocker.patch(
        "simcore_service_dask_sidecar.computational_sidecar.core.get_integration_version",
        autospec=True,
        return_value=ubuntu_task.integration_version,
    )
    future = dask_client.submit(
        run_computational_sidecar,
        ubuntu_task.docker_basic_auth,
        ubuntu_task.service_key,
        ubuntu_task.service_version,
        ubuntu_task.input_data,
        ubuntu_task.output_data_keys,
        ubuntu_task.log_file_url,
        ubuntu_task.command,
        s3_settings,
        resources={},
        boot_mode=boot_mode,
    )

    worker_name = next(iter(dask_client.scheduler_info()["workers"]))

    output_data = future.result()
    assert isinstance(output_data, TaskOutputData)

    # check that the task produces expected logs
    worker_logs = [log for _, log in dask_client.get_worker_logs()[worker_name]]  # type: ignore
    worker_logs.reverse()
    for log in ubuntu_task.expected_logs:
        r = re.compile(
            rf"\[{ubuntu_task.service_key}:{ubuntu_task.service_version} - [^\/]+\/[^\s]+ - [^\]]+\]: ({log})"
        )
        search_results = list(filter(r.search, worker_logs))
        assert (
            len(search_results) > 0
        ), f"Could not find {log} in worker_logs:\n {pformat(worker_logs, width=240)}"

    # check that the task produce the expected data, not less not more
    for k, v in ubuntu_task.expected_output_data.items():
        assert k in output_data
        assert output_data[k] == v

    s3_storage_kwargs = _s3fs_settings_from_s3_settings(s3_settings)
    for k, v in output_data.items():
        assert k in ubuntu_task.expected_output_data
        assert v == ubuntu_task.expected_output_data[k]

        # if there are file urls in the output, check they exist
        if isinstance(v, FileUrl):
            with fsspec.open(f"{v.url}", **s3_storage_kwargs) as fp:
                assert fp.details.get("size") > 0  # type: ignore


@pytest.mark.parametrize(
    "integration_version, boot_mode", [("1.0.0", BootMode.CPU)], indirect=True
)
def test_failing_service_raises_exception(
    caplog_info_level: LogCaptureFixture,
    event_loop: asyncio.AbstractEventLoop,
    mock_service_envs: None,
    dask_subsystem_mock: dict[str, MockerFixture],
    ubuntu_task_fail: ServiceExampleParam,
    s3_settings: S3Settings,
):
    with pytest.raises(ServiceRuntimeError):
        run_computational_sidecar(
            ubuntu_task_fail.docker_basic_auth,
            ubuntu_task_fail.service_key,
            ubuntu_task_fail.service_version,
            ubuntu_task_fail.input_data,
            ubuntu_task_fail.output_data_keys,
            ubuntu_task_fail.log_file_url,
            ubuntu_task_fail.command,
            s3_settings,
        )


@pytest.mark.parametrize(
    "integration_version, boot_mode", [("1.0.0", BootMode.CPU)], indirect=True
)
def test_running_service_that_generates_unexpected_data_raises_exception(
    caplog_info_level: LogCaptureFixture,
    event_loop: asyncio.AbstractEventLoop,
    mock_service_envs: None,
    dask_subsystem_mock: dict[str, MockerFixture],
    ubuntu_task_unexpected_output: ServiceExampleParam,
    s3_settings: S3Settings,
):
    with pytest.raises(ServiceBadFormattedOutputError):
        run_computational_sidecar(
            ubuntu_task_unexpected_output.docker_basic_auth,
            ubuntu_task_unexpected_output.service_key,
            ubuntu_task_unexpected_output.service_version,
            ubuntu_task_unexpected_output.input_data,
            ubuntu_task_unexpected_output.output_data_keys,
            ubuntu_task_unexpected_output.log_file_url,
            ubuntu_task_unexpected_output.command,
            s3_settings,
        )
