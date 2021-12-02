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
from typing import Dict, Iterable, List
from unittest import mock
from uuid import uuid4

import fsspec
import pytest
from _pytest.fixtures import FixtureRequest
from _pytest.logging import LogCaptureFixture
from dask_task_models_library.container_tasks.docker import DockerBasicAuth
from dask_task_models_library.container_tasks.events import (
    TaskLogEvent,
    TaskProgressEvent,
    TaskStateEvent,
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
from models_library.users import UserID
from packaging import version
from pydantic import AnyUrl
from pydantic.tools import parse_obj_as
from pytest_mock.plugin import MockerFixture
from simcore_service_dask_sidecar.computational_sidecar.docker_utils import (
    LEGACY_SERVICE_LOG_FILE_NAME,
)
from simcore_service_dask_sidecar.computational_sidecar.errors import ServiceRunError
from simcore_service_dask_sidecar.computational_sidecar.models import (
    LEGACY_INTEGRATION_VERSION,
)
from simcore_service_dask_sidecar.tasks import run_computational_sidecar
from yarl import URL

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
def dask_subsystem_mock(mocker: MockerFixture) -> Dict[str, MockerFixture]:
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
    dask_distributed_worker_mock.return_value.tasks.get.return_value = dask_task_mock

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
        "simcore_service_dask_sidecar.computational_sidecar.core.Pub",
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
    command: List[str]
    input_data: TaskInputData
    output_data_keys: TaskOutputDataSchema
    log_file_url: AnyUrl
    expected_output_data: TaskOutputData
    expected_logs: List[str]
    integration_version: version.Version


@pytest.fixture(params=[f"{LEGACY_INTEGRATION_VERSION}", "1.0.0"])
def ubuntu_task(request: FixtureRequest, ftp_server: List[URL]) -> ServiceExampleParam:
    """Creates a console task in an ubuntu distro that checks for the expected files and error in case they are missing"""
    integration_version = version.Version(request.param)
    print("Using service integration:", integration_version)
    # defines the inputs of the task
    input_data = TaskInputData.parse_obj(
        {
            "input_1": 23,
            "input_23": "a string input",
            "the_input_43": 15.0,
            "the_bool_input_54": False,
            **{
                f"some_file_input_{index+1}": FileUrl(url=f"{file}")
                for index, file in enumerate(ftp_server)
            },
        }
    )
    # check in the console that the expected files are present in the expected INPUT folder (set as ${INPUT_FOLDER} in the service)
    file_names = [file.path for file in ftp_server]
    list_of_commands = [
        "echo User: $(id $(whoami))",
        "echo Inputs:",
        "ls -tlah ${INPUT_FOLDER}",
        "echo Outputs:",
        "ls -tlah ${OUTPUT_FOLDER}",
        "echo Logs:",
        "ls -tlah ${LOG_FOLDER}",
    ]
    list_of_commands += [
        f"(test -f ${{INPUT_FOLDER}}/{file} || (echo ${{INPUT_FOLDER}}/{file} does not exists && exit 1))"
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
    output_file_url = next(iter(ftp_server)).with_path("output_file")
    expected_output_keys = TaskOutputDataSchema.parse_obj(
        {
            **{k: {"required": True} for k in jsonable_outputs.keys()},
            **{
                "pytest_file": {
                    "required": True,
                    "mapping": "a_outputfile",
                    "url": f"{output_file_url}",
                }
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
                }
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
    ]

    log_file_url = parse_obj_as(
        AnyUrl, f"{next(iter(ftp_server)).with_path('log.dat')}"
    )

    return ServiceExampleParam(
        docker_basic_auth=DockerBasicAuth(
            server_address="docker.io", username="pytest", password=""
        ),
        service_key="ubuntu",
        service_version="latest",
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
            "This is the file contents of 'file_1'",
            "This is the file contents of 'file_2'",
            "This is the file contents of 'file_3'",
        ],
        integration_version=integration_version,
    )


@pytest.fixture()
def ubuntu_task_fail(ubuntu_task: ServiceExampleParam) -> ServiceExampleParam:
    ubuntu_task.command = ["/bin/bash", "-c", "some stupid failing command"]
    return ubuntu_task


@pytest.fixture()
def caplog_info_level(caplog: LogCaptureFixture) -> Iterable[LogCaptureFixture]:
    with caplog.at_level(
        logging.INFO,
    ):
        yield caplog


def test_run_computational_sidecar_real_fct(
    caplog_info_level: LogCaptureFixture,
    loop: asyncio.AbstractEventLoop,
    mock_service_envs: None,
    dask_subsystem_mock: Dict[str, MockerFixture],
    ubuntu_task: ServiceExampleParam,
    mocker: MockerFixture,
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
    )
    mocked_get_integration_version.assert_called_once_with(
        mock.ANY,
        ubuntu_task.docker_basic_auth,
        ubuntu_task.service_key,
        ubuntu_task.service_version,
    )
    for event in [TaskProgressEvent, TaskStateEvent, TaskLogEvent]:
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

    for k, v in output_data.items():
        assert k in ubuntu_task.expected_output_data
        assert v == ubuntu_task.expected_output_data[k]

        # if there are file urls in the output, check they exist
        if isinstance(v, FileUrl):
            with fsspec.open(f"{v.url}") as fp:
                assert fp.details.get("size") > 0

    # check the task has created a log file
    with fsspec.open(f"{ubuntu_task.log_file_url}", mode="rt") as fp:
        saved_logs = fp.read()
    assert saved_logs
    for log in ubuntu_task.expected_logs:
        assert log in saved_logs


def test_run_multiple_computational_sidecar_dask(
    loop: asyncio.AbstractEventLoop,
    dask_client: Client,
    ubuntu_task: ServiceExampleParam,
    mocker: MockerFixture,
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
            resources={},
        )
        for _ in range(NUMBER_OF_TASKS)
    ]

    results = dask_client.gather(futures)

    # for result in results:
    # check that the task produce the expected data, not less not more
    for output_data in results:
        for k, v in ubuntu_task.expected_output_data.items():
            assert k in output_data
            assert output_data[k] == v


def test_run_computational_sidecar_dask(
    dask_client: Client, ubuntu_task: ServiceExampleParam, mocker: MockerFixture
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
        resources={},
    )

    worker_name = next(iter(dask_client.scheduler_info()["workers"]))

    output_data = future.result()

    # check that the task produces expected logs
    worker_logs = [log for _, log in dask_client.get_worker_logs()[worker_name]]  # type: ignore
    for log in ubuntu_task.expected_logs:
        r = re.compile(
            rf"\[{ubuntu_task.service_key}:{ubuntu_task.service_version} - .+\/.+ - .+\]: ({log})"
        )
        search_results = list(filter(r.search, worker_logs))
        assert (
            len(search_results) > 0
        ), f"Could not find {log} in worker_logs:\n {pformat(worker_logs, width=240)}"

    # check that the task produce the expected data, not less not more
    for k, v in ubuntu_task.expected_output_data.items():
        assert k in output_data
        assert output_data[k] == v

    for k, v in output_data.items():
        assert k in ubuntu_task.expected_output_data
        assert v == ubuntu_task.expected_output_data[k]

        # if there are file urls in the output, check they exist
        if isinstance(v, FileUrl):
            with fsspec.open(f"{v.url}") as fp:
                assert fp.details.get("size") > 0


def test_failing_service_raises_exception(
    caplog_info_level: LogCaptureFixture,
    loop: asyncio.AbstractEventLoop,
    mock_service_envs: None,
    dask_subsystem_mock: Dict[str, MockerFixture],
    ubuntu_task_fail: ServiceExampleParam,
    mocker: MockerFixture,
):
    mocked_get_integration_version = mocker.patch(
        "simcore_service_dask_sidecar.computational_sidecar.core.get_integration_version",
        autospec=True,
        return_value=ubuntu_task_fail.integration_version,
    )

    with pytest.raises(ServiceRunError):
        run_computational_sidecar(
            ubuntu_task_fail.docker_basic_auth,
            ubuntu_task_fail.service_key,
            ubuntu_task_fail.service_version,
            ubuntu_task_fail.input_data,
            ubuntu_task_fail.output_data_keys,
            ubuntu_task_fail.log_file_url,
            ubuntu_task_fail.command,
        )
