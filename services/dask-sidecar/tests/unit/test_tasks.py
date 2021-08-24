# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from typing import Any, Dict
from uuid import UUID, uuid4

import pytest
from simcore_service_dask_sidecar.tasks import _is_aborted_cb, run_task_in_service
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
):
    run_sidecar_mock = mocker.patch(
        "simcore_service_dask_sidecar.tasks.run_sidecar", return_value=None
    )
    dask_distributed_worker_mock = mocker.patch(
        "simcore_service_dask_sidecar.tasks.get_worker", autospec=True
    )
    dask_task_mock = mocker.patch(
        "simcore_service_dask_sidecar.tasks.TaskState", autospec=True
    )
    dask_task_mock.resource_restrictions = resource_restrictions
    dask_task_mock.retries = 1
    dask_task_mock.annotations = {"retries": 1}
    dask_distributed_worker_mock.return_value.tasks.get.return_value = dask_task_mock

    run_task_in_service(job_id, user_id, project_id, node_id)

    run_sidecar_mock.assert_called_once_with(
        job_id,
        str(user_id),
        str(project_id),
        node_id=str(node_id),
        retry=1,
        max_retries=1,
        sidecar_mode=exp_bootmode,
        is_aborted_cb=_is_aborted_cb,
    )
