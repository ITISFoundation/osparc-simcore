import asyncio

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
from pprint import pformat
from typing import Any, Dict, Iterable, List
from unittest import mock
from uuid import uuid4

import dask
import pytest
import requests
from _pytest.logging import LogCaptureFixture
from _pytest.tmpdir import TempPathFactory
from aiohttp.test_utils import loop_context
from distributed import Client
from faker import Faker
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.users import UserID
from pytest_mock.plugin import MockerFixture
from simcore_service_dask_sidecar.computational_sidecar.models import (
    FileUrl,
    TaskInputData,
    TaskOutputData,
)
from simcore_service_dask_sidecar.tasks import (
    _is_aborted_cb,
    _run_computational_sidecar_async,
    run_computational_sidecar,
    run_task_in_service,
)
from simcore_service_sidecar.boot_mode import BootMode
from yarl import URL

logger = logging.getLogger(__name__)

# TODO: real db tables
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
def dask_subsystem_mock(mocker: MockerFixture) -> None:
    dask_client_mock = mocker.patch("distributed.Client", autospec=True)

    dask_distributed_worker_mock = mocker.patch(
        "simcore_service_dask_sidecar.tasks.get_worker", autospec=True
    )
    dask_task_mock = mocker.patch(
        "simcore_service_dask_sidecar.tasks.TaskState", autospec=True
    )
    dask_task_mock.resource_restrictions = {}
    dask_distributed_worker_mock.return_value.tasks.get.return_value = dask_task_mock

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


@pytest.fixture
def dask_client() -> Client:
    print(pformat(dask.config.get("distributed")))
    with Client(nanny=False) as client:
        yield client


@dataclass
class ServiceExampleParam:
    service_key: str
    service_version: str
    command: List[str]
    input_data: TaskInputData
    output_data_keys: Dict[str, Any]
    expected_output_data: TaskOutputData
    expected_logs: List[str]


@pytest.fixture(scope="module")
def loop() -> asyncio.AbstractEventLoop:
    with loop_context() as loop:
        yield loop


@pytest.fixture(scope="module")
async def directory_server(
    loop, tmp_path_factory: TempPathFactory
) -> Iterable[List[URL]]:
    faker = Faker()
    files = ["file_1", "file_2", "file_3"]
    base_url = URL("http://localhost:8999")
    directory_path = tmp_path_factory.mktemp("directory_server")
    assert directory_path.exists()
    for fn in files:
        with (directory_path / fn).open("wt") as f:
            f.write(f"This file is named: {fn}\n")
            for s in faker.sentences():
                f.write(f"{s}\n")

    cmd = [sys.executable, "-m", "http.server", "8999"]

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


@pytest.fixture()
def ubuntu_task(directory_server: List[URL]) -> ServiceExampleParam:
    file_names = [file.path for file in directory_server]
    check_input_file_command = " && ".join(
        [
            f"(test -f ${{INPUT_FOLDER}}/{file} || (echo ${{INPUT_FOLDER}}/{file} does not exists && exit 1))"
            for file in file_names
        ]
    )
    echo_input_files_in_log_command = " && ".join(
        [f"echo $(cat ${{INPUT_FOLDER}}/{file})" for file in file_names]
    )

    command = [
        "/bin/bash",
        "-c",
        "echo User: $(id $(whoami)) && "
        "(test -f ${INPUT_FOLDER}/inputs.json || (echo ${INPUT_FOLDER}/inputs.json file does not exists && exit 1)) && "
        "echo $(cat ${INPUT_FOLDER}/inputs.json) && "
        f"{check_input_file_command} && "
        f"{echo_input_files_in_log_command} &&"
        'echo {\\"pytest_output_1\\":\\"is quite an amazing feat\\"} > ${OUTPUT_FOLDER}/outputs.json',
    ]
    input_data = TaskInputData.parse_obj(
        {
            "input_1": 23,
            "input_23": "a string input",
            "the_input_43": 15.0,
            "the_bool_input_54": False,
            **{
                f"some_file_input_{index+1}": FileUrl(url=f"{file}")
                for index, file in enumerate(directory_server)
            },
        }
    )
    return ServiceExampleParam(
        service_key="ubuntu",
        service_version="latest",
        command=command,
        input_data=input_data,
        output_data_keys={"pytest_output_1": {"type": str}},
        expected_output_data=TaskOutputData.parse_obj(
            {"pytest_output_1": "is quite an amazing feat"}
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
async def test_run_computational_sidecar_real_fct(
    dask_subsystem_mock: None, task: ServiceExampleParam, caplog: LogCaptureFixture
):
    caplog.set_level(logging.INFO)
    output_data = await _run_computational_sidecar_async(
        task.service_key,
        task.service_version,
        task.input_data,
        task.output_data_keys,
        task.command,
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

    for k, v in task.expected_output_data.items():
        assert k in output_data
        if isinstance(v, re.Pattern):
            assert v.match(f"{output_data[k]}")
        else:
            assert output_data[k] == v

    for k, v in output_data.items():
        assert k in task.expected_output_data
        assert v == task.expected_output_data[k]


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
async def test_run_computational_sidecar_dask(
    dask_client: Client, task: ServiceExampleParam
):
    future = dask_client.submit(
        run_computational_sidecar,
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

    for k, v in task.expected_output_data.items():
        assert k in output_data
        if isinstance(v, re.Pattern):
            assert v.match(f"{output_data[k]}")
        else:
            assert output_data[k] == v

    for k, v in output_data.items():
        assert k in task.expected_output_data
        assert v == task.expected_output_data[k]


@pytest.mark.parametrize(
    "resource_restrictions, exp_bootmode",
    [
        ({}, BootMode.CPU),
        ({"MPI": 0}, BootMode.CPU),
        (
            {"MPI": 1, "GPU": 2},
            BootMode.MPI,
        ),  # FIXME: this is currently so... but should change
        (
            {"MPI": 0, "GPU": 2},
            BootMode.GPU,
        ),  # FIXME: this is currently so... but should change
    ],
)
def test_run_task_in_service(
    loop,
    job_id: str,
    user_id: UserID,
    project_id: ProjectID,
    node_id: NodeID,
    mocker,
    resource_restrictions: Dict[str, Any],
    exp_bootmode: BootMode,
    dask_subsystem_mock: Dict[str, mock.Mock],
):
    run_sidecar_mock = mocker.patch(
        "simcore_service_dask_sidecar.tasks.run_sidecar", return_value=None
    )

    dask_subsystem_mock["dask_task"].resource_restrictions = resource_restrictions
    dask_subsystem_mock["dask_task"].retries = 1
    dask_subsystem_mock["dask_task"].annotations = {"retries": 1}

    run_task_in_service(job_id, user_id, project_id, node_id)

    run_sidecar_mock.assert_called_once_with(
        job_id,
        str(user_id),
        str(project_id),
        node_id=str(node_id),
        retry=0,
        max_retries=1,
        sidecar_mode=exp_bootmode,
        is_aborted_cb=_is_aborted_cb,
    )
