# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=no-value-for-parameter
# pylint:disable=protected-access
# pylint:disable=too-many-arguments
# pylint:disable=no-name-in-module
# pylint: disable=too-many-statements

from unittest import mock

import pytest
from _helpers import PublishedProject
from fastapi import FastAPI
from models_library.clusters import DEFAULT_CLUSTER_ID
from pytest_mock import MockerFixture
from simcore_service_director_v2.models.comp_runs import RunMetadataDict
from simcore_service_director_v2.modules.comp_scheduler._manager import run_new_pipeline
from simcore_service_director_v2.modules.comp_scheduler._worker import (
    _get_scheduler_worker,
)

pytest_simcore_core_services_selection = ["postgres", "rabbit", "redis"]
pytest_simcore_ops_services_selection = ["adminer"]


async def test_worker_starts_and_stops(initialized_app: FastAPI):
    assert _get_scheduler_worker(initialized_app) is not None


@pytest.fixture
def mock_schedule_pipeline(mocker: MockerFixture) -> mock.Mock:
    mock_scheduler_worker = mock.Mock()
    mock_scheduler_worker.schedule_pipeline = mocker.AsyncMock(return_value=True)
    return mock_scheduler_worker


@pytest.fixture
def mocked_get_scheduler_worker(
    mocker: MockerFixture,
    mock_schedule_pipeline: mock.Mock,
) -> mock.Mock:
    # Mock `_get_scheduler_worker` to return our mock scheduler
    return mocker.patch(
        "simcore_service_director_v2.modules.comp_scheduler._worker._get_scheduler_worker",
        return_value=mock_schedule_pipeline,
    )


async def test_worker_properly_calls_scheduler_api(
    with_disabled_auto_scheduling: mock.Mock,
    initialized_app: FastAPI,
    mocked_get_scheduler_worker: mock.Mock,
    published_project: PublishedProject,
    run_metadata: RunMetadataDict,
):
    assert published_project.project.prj_owner
    await run_new_pipeline(
        initialized_app,
        user_id=published_project.project.prj_owner,
        project_id=published_project.project.uuid,
        cluster_id=DEFAULT_CLUSTER_ID,
        run_metadata=run_metadata,
        use_on_demand_clusters=False,
    )
    mocked_get_scheduler_worker.assert_called_once_with(initialized_app)
    mocked_get_scheduler_worker.return_value.schedule_pipeline.assert_called_once_with(
        user_id=published_project.project.prj_owner,
        project_id=published_project.project.uuid,
        iteration=1,
    )
