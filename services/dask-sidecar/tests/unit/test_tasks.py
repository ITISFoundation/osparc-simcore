import asyncio
import json

# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=no-member
import logging
import re
import subprocess

# copied out from dask
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from pprint import pformat
from typing import Dict, Iterable, List, Optional
from unittest.mock import call
from uuid import uuid4

import dask
import fsspec
import pytest
import requests
from _pytest.logging import LogCaptureFixture
from _pytest.monkeypatch import MonkeyPatch
from _pytest.tmpdir import TempPathFactory
from aiohttp.test_utils import loop_context
from dask_task_models_library.container_tasks.docker import DockerBasicAuth
from dask_task_models_library.container_tasks.events import TaskStateEvent
from dask_task_models_library.container_tasks.io import (
    FileUrl,
    TaskInputData,
    TaskOutputData,
    TaskOutputDataSchema,
)
from distributed import Client
from faker import Faker
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.projects_state import RunningState
from models_library.users import UserID
from pytest_localftpserver.servers import ProcessFTPServer
from pytest_mock.plugin import MockerFixture
from simcore_service_dask_sidecar.tasks import run_computational_sidecar
from yarl import URL

logger = logging.getLogger(__name__)


@pytest.fixture
def mock_service_envs(
    mock_env_devel_environment: Dict[str, Optional[str]],
    monkeypatch: MonkeyPatch,
    mocker: MockerFixture,
    tmp_path_factory: TempPathFactory,
) -> None:

    # Variables directly define inside Dockerfile
    monkeypatch.setenv("SC_BOOT_MODE", "debug-ptvsd")

    monkeypatch.setenv("SWARM_STACK_NAME", "simcore")
    monkeypatch.setenv("SIDECAR_LOGLEVEL", "DEBUG")
    monkeypatch.setenv("SIDECAR_HOST_HOSTNAME_PATH", "/home/scu/hostname")
    monkeypatch.setenv(
        "SIDECAR_COMP_SERVICES_SHARED_VOLUME_NAME", "simcore_computational_shared_data"
    )

    shared_data_folder = tmp_path_factory.mktemp("pytest_comp_shared_data")
    assert shared_data_folder.exists()
    monkeypatch.setenv("SIDECAR_COMP_SERVICES_SHARED_FOLDER", f"{shared_data_folder}")
    mocker.patch(
        "simcore_service_dask_sidecar.computational_sidecar.core.get_computational_shared_data_mount_point",
        return_value=shared_data_folder,
    )


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
        "simcore_service_dask_sidecar.tasks.get_worker", autospec=True
    )
    dask_task_mock = mocker.patch(
        "simcore_service_dask_sidecar.tasks.TaskState", autospec=True
    )
    dask_task_mock.resource_restrictions = {}
    dask_distributed_worker_mock.return_value.tasks.get.return_value = dask_task_mock

    # mock dask loggers
    dask_tasks_logger = mocker.patch(
        "simcore_service_dask_sidecar.tasks.log",
        logging.getLogger(__name__),
    )

    dask_core_logger = mocker.patch(
        "simcore_service_dask_sidecar.computational_sidecar.core.logger",
        logging.getLogger(__name__),
    )

    dask__docker_utils_logger = mocker.patch(
        "simcore_service_dask_sidecar.computational_sidecar.docker_utils.logger",
        logging.getLogger(__name__),
    )

    # mock dask event worker
    dask_distributed_worker_events_mock = mocker.patch(
        "dask_task_models_library.container_tasks.events.get_worker", autospec=True
    )
    dask_distributed_worker_events_mock.return_value.get_current_task.return_value = (
        "pytest_jobid"
    )
    # mock dask event publishing
    dask_utils_publish_event_mock = mocker.patch(
        "simcore_service_dask_sidecar.computational_sidecar.core.publish_event",
        autospec=True,
        return_value=None,
    )

    return {
        "dask_client": dask_client_mock,
        "dask_task_state": dask_task_mock,
        "dask_event_publish": dask_utils_publish_event_mock,
    }


@pytest.fixture
def dask_client() -> Client:
    print(pformat(dask.config.get("distributed")))
    with Client(nanny=False) as client:
        yield client


@dataclass
class ServiceExampleParam:
    docker_basic_auth: DockerBasicAuth
    service_key: str
    service_version: str
    command: List[str]
    input_data: TaskInputData
    output_data_keys: TaskOutputDataSchema
    expected_output_data: TaskOutputData
    expected_logs: List[str]


@pytest.fixture(scope="module")
def loop() -> asyncio.AbstractEventLoop:
    with loop_context() as loop:
        yield loop


@pytest.fixture(scope="module")
def http_server(tmp_path_factory: TempPathFactory) -> Iterable[List[URL]]:
    faker = Faker()
    files = ["file_1", "file_2", "file_3"]
    directory_path = tmp_path_factory.mktemp("http_server")
    assert directory_path.exists()
    for fn in files:
        with (directory_path / fn).open("wt") as f:
            f.write(f"This file is named: {fn}\n")
            for s in faker.sentences():
                f.write(f"{s}\n")

    cmd = [sys.executable, "-m", "http.server", "8999"]

    base_url = URL("http://localhost:8999")
    with subprocess.Popen(cmd, cwd=directory_path) as p:
        timeout = 10
        while True:
            try:
                requests.get(f"{base_url}")
                break
            except requests.exceptions.ConnectionError as e:
                time.sleep(0.1)
                timeout -= 0.1
                if timeout < 0:
                    raise RuntimeError("Server did not appear") from e
        # the server must be up
        yield [base_url.with_path(f) for f in files]
        # cleanup now, sometimes it hangs
        p.kill()


@pytest.fixture(scope="module")
def ftp_server(ftpserver: ProcessFTPServer) -> List[URL]:
    faker = Faker()

    files = ["file_1", "file_2", "file_3"]
    ftp_server_base_url = ftpserver.get_login_data(style="url")
    list_of_file_urls = [f"{ftp_server_base_url}/{filename}.txt" for filename in files]
    with fsspec.open_files(list_of_file_urls, "wt") as open_files:
        for index, fp in enumerate(open_files):
            fp.write(f"This file is named: {files[index]}\n")
            for s in faker.sentences():
                fp.write(f"{s}\n")

    return [URL(f) for f in list_of_file_urls]


@pytest.fixture()
def ubuntu_task(http_server: List[URL], ftp_server: List[URL]) -> ServiceExampleParam:
    file_names = [file.path for file in ftp_server]
    check_input_file_command = " && ".join(
        [
            f"(test -f ${{INPUT_FOLDER}}/{file} || (echo ${{INPUT_FOLDER}}/{file} does not exists && exit 1))"
            for file in file_names
        ]
    )
    echo_input_files_in_log_command = " && ".join(
        [f"echo $(cat ${{INPUT_FOLDER}}/{file})" for file in file_names]
    )

    jsonable_outputs = {
        "pytest_string": "is quite an amazing feat",
        "pytest_integer": 432,
        "pytest_float": 3.2,
        "pytest_bool": False,
    }
    echo_jsonable_outputs_command = json.dumps(jsonable_outputs).replace('"', '\\"')

    command = [
        "/bin/bash",
        "-c",
        "echo User: $(id $(whoami)) && "
        "(test -f ${INPUT_FOLDER}/inputs.json || (echo ${INPUT_FOLDER}/inputs.json file does not exists && exit 1)) && "
        "echo $(cat ${INPUT_FOLDER}/inputs.json) && "
        f"{check_input_file_command} && "
        f"{echo_input_files_in_log_command} && "
        f"echo {echo_jsonable_outputs_command} > ${{OUTPUT_FOLDER}}/outputs.json && "
        "echo 'some data for the output file' > ${OUTPUT_FOLDER}/a_outputfile",
    ]
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

    output_file_url = next(iter(ftp_server)).with_path("output_file")

    return ServiceExampleParam(
        docker_basic_auth=DockerBasicAuth(
            server_address="docker.io", username="pytest", password=""
        ),
        service_key="ubuntu",
        service_version="latest",
        command=command,
        input_data=input_data,
        output_data_keys=TaskOutputDataSchema.parse_obj(
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
        ),
        expected_output_data=TaskOutputData.parse_obj(
            {
                **jsonable_outputs,
                **{
                    "pytest_file": {
                        "url": f"{output_file_url}",
                        "file_mapping": "a_outputfile",
                    }
                },
            }
        ),
        expected_logs=[
            '{"input_1": 23, "input_23": "a string input", "the_input_43": 15.0, "the_bool_input_54": false}',
            "This file is named: file_1",
            "This file is named: file_2",
            "This file is named: file_3",
        ],
    )


@pytest.mark.parametrize(
    "task",
    [
        pytest.lazy_fixture("ubuntu_task"),
    ],
)
def test_run_computational_sidecar_real_fct(
    loop: asyncio.AbstractEventLoop,
    mock_service_envs: None,
    dask_subsystem_mock: Dict[str, MockerFixture],
    task: ServiceExampleParam,
    caplog: LogCaptureFixture,
):
    caplog.set_level(logging.INFO)
    output_data = run_computational_sidecar(
        task.docker_basic_auth,
        task.service_key,
        task.service_version,
        task.input_data,
        task.output_data_keys,
        task.command,
    )
    dask_subsystem_mock["dask_event_publish"].assert_has_calls(
        [call(TaskStateEvent.from_dask_worker(state=RunningState.STARTED))]
    )

    # check that the task produces expected logs
    for log in task.expected_logs:
        r = re.compile(
            rf"\[{task.service_key}:{task.service_version} - .+\/.+\]: (.+) ({log})"
        )
        search_results = list(filter(r.search, caplog.messages))
        assert (
            len(search_results) > 0
        ), f"Could not find {log} in worker_logs:\n {pformat(caplog.messages, width=240)}"
    for log in task.expected_logs:
        assert re.search(
            rf"\[{task.service_key}:{task.service_version} - .+\/.+\]: (.+) ({log})",
            caplog.text,
        )
    # check that the task produce the expected data, not less not more
    for k, v in task.expected_output_data.items():
        assert k in output_data
        assert output_data[k] == v

    for k, v in output_data.items():
        assert k in task.expected_output_data
        assert v == task.expected_output_data[k]

        # if there are file urls in the output, check they exist
        if isinstance(v, FileUrl):
            with fsspec.open(f"{v.url}") as fp:
                assert fp.details.get("size") > 0


@pytest.mark.parametrize(
    "task",
    [
        pytest.lazy_fixture("ubuntu_task"),
        # ServiceExampleParam(
        #     service_key="itisfoundation/sleeper",
        #     service_version="2.1.1",
        #     command=[],
        #     input_data={"input_2": 2, "input_4": 1},
        #     output_data_keys={
        #         "output_1": {"type": Path, "name": "single_number.txt"},
        #         "output_2": {"type": int},
        #     },
        #     expected_output_data={
        #         "output_1": re.compile(r".+/single_number.txt"),
        #         "output_2": re.compile(r"\d"),
        #     },
        #     expected_logs=["Remaining sleep time"],
        # ),
    ],
)
def test_run_computational_sidecar_dask(
    mock_service_envs: None, dask_client: Client, task: ServiceExampleParam
):
    future = dask_client.submit(
        run_computational_sidecar,
        task.docker_basic_auth,
        task.service_key,
        task.service_version,
        task.input_data,
        task.output_data_keys,
        task.command,
        resources={},
    )

    worker_name = next(iter(dask_client.scheduler_info()["workers"]))

    output_data = future.result()

    # check that the task produces expected logs
    worker_logs = [log for _, log in dask_client.get_worker_logs()[worker_name]]
    for log in task.expected_logs:
        r = re.compile(
            rf"\[{task.service_key}:{task.service_version} - .+\/.+\]: (.+) ({log})"
        )
        search_results = list(filter(r.search, worker_logs))
        assert (
            len(search_results) > 0
        ), f"Could not find {log} in worker_logs:\n {pformat(worker_logs, width=240)}"

    # check that the task produce the expected data, not less not more
    for k, v in task.expected_output_data.items():
        assert k in output_data
        assert output_data[k] == v

    for k, v in output_data.items():
        assert k in task.expected_output_data
        assert v == task.expected_output_data[k]

        # if there are file urls in the output, check they exist
        if isinstance(v, FileUrl):
            with fsspec.open(f"{v.url}") as fp:
                assert fp.details.get("size") > 0


def test_uploading_withfsspec(ftpserver: ProcessFTPServer):
    ftp_server_base_url = ftpserver.get_login_data(style="url")
    open_file = fsspec.open(
        f"{ftp_server_base_url}/test_file.txt",
        "wt",
    )
    with open_file as dst:
        dst.write("some test")
    uploaded_file_path = Path(ftpserver.server_home, "test_file.txt")
    with uploaded_file_path.open() as uploaded:
        assert uploaded.read() == "some test"
