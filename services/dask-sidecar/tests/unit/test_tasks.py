import logging
import re

# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
from typing import Any, Dict, List
from unittest import mock
from uuid import UUID, uuid4

import pytest
from pytest_mock.plugin import MockerFixture
from simcore_service_dask_sidecar.tasks import (
    _is_aborted_cb,
    run_computational_sidecar,
    run_task_in_service,
)
from simcore_service_sidecar.boot_mode import BootMode


# TODO: real db tables
@pytest.fixture
def job_id() -> str:
    return "some_incredible_string"


@pytest.fixture
def user_id() -> int:
    return 1


@pytest.fixture
def project_id() -> UUID:
    return uuid4()


@pytest.fixture
def node_id() -> UUID:
    return uuid4()


@pytest.fixture()
def dask_subsystem_mock(mocker: MockerFixture) -> Dict[str, mock.Mock]:
    dask_distributed_worker_mock = mocker.patch(
        "simcore_service_dask_sidecar.tasks.get_worker", autospec=True
    )
    dask_task_mock = mocker.patch(
        "simcore_service_dask_sidecar.tasks.TaskState", autospec=True
    )
    dask_task_mock.resource_restrictions = {}

    dask_distributed_worker_mock.return_value.tasks.get.return_value = dask_task_mock

    return {
        "dask_task": dask_task_mock,
        "dask_distributed_worker": dask_distributed_worker_mock,
    }


@pytest.mark.parametrize(
    "service_key, service_version, command, input_data, expected_output_data, expected_logs",
    [
        (
            "ubuntu",
            "latest",
            ["/bin/bash", "-c", "echo hello"],
            {},
            {},
            ["hello"],
        ),
        (
            "itisfoundation/sleeper",
            "2.1.1",
            [],
            {},
            {},
            ["hello"],
        ),
    ],
)
async def test_run_computational_sidecar(
    dask_subsystem_mock: Dict[str, mock.Mock],
    service_key: str,
    service_version: str,
    command: List[str],
    input_data: Dict[str, Any],
    expected_output_data: Dict[str, Any],
    expected_logs: List[str],
    caplog,
):
    caplog.set_level(logging.INFO)
    output_data = await run_computational_sidecar(
        service_key=service_key,
        service_version=service_version,
        input_data=input_data,
        command=command,
    )

    # check that expected logs are there
    for log in expected_logs:
        assert re.search(
            rf"\[{service_key}:{service_version} - .+\/.+\]: {log}", caplog.text
        )

    assert output_data == expected_output_data


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
    user_id: int,
    project_id: UUID,
    node_id: UUID,
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
