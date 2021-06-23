# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from uuid import UUID, uuid4

import pytest


# TODO: real db tables
@pytest.fixture
def job_id() -> int:
    return 1


@pytest.fixture
def user_id() -> int:
    return 1


@pytest.fixture
def project_id() -> UUID:
    return uuid4()


@pytest.fixture
def node_id() -> UUID:
    return uuid4()


def test_run_task_in_service(
    job_id: int, user_id: int, project_id: UUID, node_id: UUID, mocker
):
    run_sidecar_mock = mocker.patch(
        "simcore_service_sidecar.cli.run_sidecar", return_value=None
    )

    from simcore_service_dask_sidecar.tasks import run_task_in_service

    run_task_in_service(job_id, user_id, project_id, node_id)
