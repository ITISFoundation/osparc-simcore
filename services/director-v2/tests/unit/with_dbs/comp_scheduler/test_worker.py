# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=no-value-for-parameter
# pylint:disable=protected-access
# pylint:disable=too-many-arguments
# pylint:disable=no-name-in-module
# pylint: disable=too-many-statements

import asyncio
from collections.abc import Awaitable, Callable
from unittest import mock

import pytest
from _helpers import PublishedProject
from fastapi import FastAPI
from models_library.clusters import DEFAULT_CLUSTER_ID
from pytest_mock import MockerFixture
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from simcore_service_director_v2.models.comp_runs import RunMetadataDict
from simcore_service_director_v2.modules.comp_scheduler._manager import run_new_pipeline
from simcore_service_director_v2.modules.comp_scheduler._models import (
    SchedulePipelineRabbitMessage,
)
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


async def test_worker_properly_autocalls_scheduler_api(
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
    mocked_get_scheduler_worker.return_value.apply.assert_called_once_with(
        user_id=published_project.project.prj_owner,
        project_id=published_project.project.uuid,
        iteration=1,
    )


@pytest.fixture
async def mocked_scheduler_api(mocker: MockerFixture) -> mock.Mock:
    return mocker.patch(
        "simcore_service_director_v2.modules.comp_scheduler._scheduler_base.BaseCompScheduler.apply"
    )


@pytest.fixture
def with_scheduling_concurrency(
    mock_env: EnvVarsDict, monkeypatch: pytest.MonkeyPatch, scheduling_concurrency: int
) -> EnvVarsDict:
    return mock_env | setenvs_from_dict(
        monkeypatch,
        {"COMPUTATIONAL_BACKEND_SCHEDULING_CONCURRENCY": f"{scheduling_concurrency}"},
    )


@pytest.mark.parametrize("scheduling_concurrency", [1, 50, 100])
@pytest.mark.parametrize(
    "queue_name", [SchedulePipelineRabbitMessage.get_channel_name()]
)
async def test_worker_scheduling_parallelism(
    scheduling_concurrency: int,
    with_scheduling_concurrency: EnvVarsDict,
    with_disabled_auto_scheduling: mock.Mock,
    mocked_scheduler_api: mock.Mock,
    initialized_app: FastAPI,
    publish_project: Callable[[], Awaitable[PublishedProject]],
    run_metadata: RunMetadataDict,
    ensure_parametrized_queue_is_empty: None,
):
    with_disabled_auto_scheduling.assert_called_once()

    async def _side_effect(*args, **kwargs):
        await asyncio.sleep(10)

    mocked_scheduler_api.side_effect = _side_effect

    async def _project_pipeline_creation_workflow() -> None:
        published_project = await publish_project()
        assert published_project.project.prj_owner
        await run_new_pipeline(
            initialized_app,
            user_id=published_project.project.prj_owner,
            project_id=published_project.project.uuid,
            cluster_id=DEFAULT_CLUSTER_ID,
            run_metadata=run_metadata,
            use_on_demand_clusters=False,
        )

    await asyncio.gather(
        *(_project_pipeline_creation_workflow() for _ in range(scheduling_concurrency))
    )
    mocked_scheduler_api.assert_called()
    assert mocked_scheduler_api.call_count == scheduling_concurrency
