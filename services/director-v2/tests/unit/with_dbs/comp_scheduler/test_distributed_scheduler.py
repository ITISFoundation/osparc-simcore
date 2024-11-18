# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=no-value-for-parameter
# pylint:disable=protected-access
# pylint:disable=too-many-arguments
# pylint:disable=no-name-in-module
# pylint: disable=too-many-statements


import asyncio
import datetime
import logging
from collections.abc import AsyncIterator, Callable
from typing import Any, Awaitable
from unittest import mock

import pytest
import sqlalchemy as sa
from _helpers import PublishedProject
from fastapi import FastAPI
from models_library.clusters import DEFAULT_CLUSTER_ID
from models_library.projects import ProjectAtDB
from models_library.projects_state import RunningState
from pytest_mock.plugin import MockerFixture
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from servicelib.rabbitmq._client import RabbitMQClient
from servicelib.redis import CouldNotAcquireLockError
from servicelib.utils import limited_gather
from settings_library.rabbit import RabbitSettings
from settings_library.redis import RedisSettings
from simcore_postgres_database.models.comp_runs import comp_runs
from simcore_service_director_v2.core.errors import PipelineNotFoundError
from simcore_service_director_v2.models.comp_pipelines import CompPipelineAtDB
from simcore_service_director_v2.models.comp_runs import CompRunsAtDB, RunMetadataDict
from simcore_service_director_v2.modules.comp_scheduler._distributed_scheduler import (
    SCHEDULER_INTERVAL,
    run_new_pipeline,
    schedule_pipelines,
    stop_pipeline,
)
from simcore_service_director_v2.modules.comp_scheduler._models import (
    SchedulePipelineRabbitMessage,
)
from sqlalchemy.ext.asyncio import AsyncEngine

pytest_simcore_core_services_selection = ["postgres", "rabbit", "redis"]
pytest_simcore_ops_services_selection = ["adminer", "redis-commander"]


@pytest.fixture
def mock_env(
    mock_env: EnvVarsDict,
    monkeypatch: pytest.MonkeyPatch,
    fake_s3_envs: EnvVarsDict,
    postgres_db: sa.engine.Engine,
    postgres_host_config: dict[str, str],
    rabbit_service: RabbitSettings,
    redis_service: RedisSettings,
) -> EnvVarsDict:
    return mock_env | setenvs_from_dict(
        monkeypatch,
        {k: f"{v}" for k, v in fake_s3_envs.items()}
        | {
            "COMPUTATIONAL_BACKEND_ENABLED": True,
            "COMPUTATIONAL_BACKEND_DASK_CLIENT_ENABLED": True,
        },
    )


@pytest.fixture
def with_disabled_auto_scheduling(mocker: MockerFixture) -> mock.Mock:
    mocker.patch(
        "simcore_service_director_v2.modules.comp_scheduler.shutdown_manager",
    )
    return mocker.patch(
        "simcore_service_director_v2.modules.comp_scheduler.setup_manager",
    )


@pytest.fixture
def with_disabled_scheduler_worker(mocker: MockerFixture) -> mock.Mock:
    return mocker.patch(
        "simcore_service_director_v2.modules.comp_scheduler.setup_worker",
        autospec=True,
    )


@pytest.fixture
async def scheduler_rabbit_client_parser(
    create_rabbitmq_client: Callable[[str], RabbitMQClient], mocker: MockerFixture
) -> AsyncIterator[mock.AsyncMock]:
    client = create_rabbitmq_client("scheduling_pytest_consumer")
    mock = mocker.AsyncMock(return_value=True)
    queue_name = await client.subscribe(
        SchedulePipelineRabbitMessage.get_channel_name(), mock, exclusive_queue=False
    )
    yield mock
    await client.unsubscribe(queue_name)


async def _assert_comp_runs(
    sqlalchemy_async_engine: AsyncEngine, *, expected_total: int
) -> list[CompRunsAtDB]:
    async with sqlalchemy_async_engine.connect() as conn:
        list_of_comp_runs = [
            CompRunsAtDB.from_orm(row)
            for row in await conn.execute(sa.select(comp_runs))
        ]
    assert len(list_of_comp_runs) == expected_total
    return list_of_comp_runs


async def _assert_comp_runs_empty(sqlalchemy_async_engine: AsyncEngine) -> None:
    await _assert_comp_runs(sqlalchemy_async_engine, expected_total=0)


async def test_schedule_pipelines_empty_db(
    with_disabled_auto_scheduling: mock.Mock,
    initialized_app: FastAPI,
    scheduler_rabbit_client_parser: mock.AsyncMock,
    sqlalchemy_async_engine: AsyncEngine,
):
    with_disabled_auto_scheduling.assert_called_once()
    await _assert_comp_runs_empty(sqlalchemy_async_engine)

    await schedule_pipelines(initialized_app)

    # check nothing was distributed
    scheduler_rabbit_client_parser.assert_not_called()

    # check comp_runs is still empty
    await _assert_comp_runs_empty(sqlalchemy_async_engine)


async def test_schedule_pipelines_concurently_runs_exclusively_and_raises(
    with_disabled_auto_scheduling: mock.Mock,
    initialized_app: FastAPI,
    mocker: MockerFixture,
    monkeypatch: pytest.MonkeyPatch,
):
    CONCURRENCY = 5
    # NOTE: this ensure no flakyness as empty scheduling is very fast
    original_function = limited_gather

    async def slow_limited_gather(*args, **kwargs):
        result = await original_function(*args, **kwargs)
        await asyncio.sleep(3)  # to ensure flakyness does not occur
        return result

    mock_function = mocker.patch(
        "simcore_service_director_v2.modules.comp_scheduler._distributed_scheduler.limited_gather",
        autospec=True,
        side_effect=slow_limited_gather,
    )

    results = await asyncio.gather(
        *(schedule_pipelines(initialized_app) for _ in range(CONCURRENCY)),
        return_exceptions=True,
    )

    assert results.count(None) == 1, f"Only one task should have run: {results}"
    for r in results:
        if r:
            assert isinstance(r, CouldNotAcquireLockError)
    mock_function.assert_called_once()


async def test_schedule_pipelines(
    with_disabled_auto_scheduling: mock.Mock,
    with_disabled_scheduler_worker: mock.Mock,
    initialized_app: FastAPI,
    published_project: PublishedProject,
    sqlalchemy_async_engine: AsyncEngine,
    run_metadata: RunMetadataDict,
    scheduler_rabbit_client_parser: mock.AsyncMock,
):
    await _assert_comp_runs_empty(sqlalchemy_async_engine)
    assert published_project.project.prj_owner
    # now we schedule a pipeline
    await run_new_pipeline(
        initialized_app,
        user_id=published_project.project.prj_owner,
        project_id=published_project.project.uuid,
        cluster_id=DEFAULT_CLUSTER_ID,
        run_metadata=run_metadata,
        use_on_demand_clusters=False,
    )
    # this directly schedule a new pipeline
    scheduler_rabbit_client_parser.assert_called_once_with(
        SchedulePipelineRabbitMessage(
            user_id=published_project.project.prj_owner,
            project_id=published_project.project.uuid,
            iteration=1,
        ).body()
    )
    scheduler_rabbit_client_parser.reset_mock()
    comp_runs = await _assert_comp_runs(sqlalchemy_async_engine, expected_total=1)
    comp_run = comp_runs[0]
    assert comp_run.project_uuid == published_project.project.uuid
    assert comp_run.user_id == published_project.project.prj_owner
    assert comp_run.iteration == 1
    assert comp_run.cancelled is None
    assert comp_run.cluster_id == DEFAULT_CLUSTER_ID
    assert comp_run.metadata == run_metadata
    assert comp_run.result is RunningState.PUBLISHED
    assert comp_run.last_scheduled is not None
    start_schedule_time = comp_run.last_scheduled
    start_modified_time = comp_run.modified

    # this will now not schedule the pipeline since it was last scheduled
    await schedule_pipelines(initialized_app)
    scheduler_rabbit_client_parser.assert_not_called()
    comp_runs = await _assert_comp_runs(sqlalchemy_async_engine, expected_total=1)
    comp_run = comp_runs[0]
    assert comp_run.last_scheduled == start_schedule_time, "scheduled time changed!"
    assert comp_run.cancelled is None
    assert comp_run.modified == start_modified_time

    # this will now schedule the pipeline since the time passed
    await asyncio.sleep(SCHEDULER_INTERVAL.total_seconds() + 1)
    await schedule_pipelines(initialized_app)
    scheduler_rabbit_client_parser.assert_called_once_with(
        SchedulePipelineRabbitMessage(
            user_id=published_project.project.prj_owner,
            project_id=published_project.project.uuid,
            iteration=1,
        ).body()
    )
    scheduler_rabbit_client_parser.reset_mock()
    comp_runs = await _assert_comp_runs(sqlalchemy_async_engine, expected_total=1)
    comp_run = comp_runs[0]
    assert comp_run.last_scheduled is not None
    assert comp_run.last_scheduled > start_schedule_time
    last_schedule_time = comp_run.last_scheduled
    assert comp_run.cancelled is None
    assert comp_run.modified > start_modified_time

    # now we stop the pipeline, which should instantly trigger a schedule
    await stop_pipeline(
        initialized_app,
        user_id=published_project.project.prj_owner,
        project_id=published_project.project.uuid,
    )
    await schedule_pipelines(initialized_app)
    scheduler_rabbit_client_parser.assert_called_once_with(
        SchedulePipelineRabbitMessage(
            user_id=published_project.project.prj_owner,
            project_id=published_project.project.uuid,
            iteration=1,
        ).body()
    )
    scheduler_rabbit_client_parser.reset_mock()
    comp_runs = await _assert_comp_runs(sqlalchemy_async_engine, expected_total=1)
    comp_run = comp_runs[0]
    assert comp_run.last_scheduled is not None
    assert comp_run.last_scheduled > last_schedule_time
    assert comp_run.cancelled is not None


async def test_empty_pipeline_is_not_scheduled(
    with_disabled_auto_scheduling: mock.Mock,
    with_disabled_scheduler_worker: mock.Mock,
    initialized_app: FastAPI,
    registered_user: Callable[..., dict[str, Any]],
    project: Callable[..., Awaitable[ProjectAtDB]],
    pipeline: Callable[..., CompPipelineAtDB],
    run_metadata: RunMetadataDict,
    sqlalchemy_async_engine: AsyncEngine,
    scheduler_rabbit_client_parser: mock.AsyncMock,
    caplog: pytest.LogCaptureFixture,
):
    await _assert_comp_runs_empty(sqlalchemy_async_engine)
    user = registered_user()
    empty_project = await project(user)

    # the project is not in the comp_pipeline, therefore scheduling it should fail
    with pytest.raises(PipelineNotFoundError):
        await run_new_pipeline(
            initialized_app,
            user_id=user["id"],
            project_id=empty_project.uuid,
            cluster_id=DEFAULT_CLUSTER_ID,
            run_metadata=run_metadata,
            use_on_demand_clusters=False,
        )
    await _assert_comp_runs_empty(sqlalchemy_async_engine)
    scheduler_rabbit_client_parser.assert_not_called()

    # create the empty pipeline now
    pipeline(project_id=f"{empty_project.uuid}")

    # creating a run with an empty pipeline is useless, check the scheduler is not kicking in
    with caplog.at_level(logging.WARNING):
        await run_new_pipeline(
            initialized_app,
            user_id=user["id"],
            project_id=empty_project.uuid,
            cluster_id=DEFAULT_CLUSTER_ID,
            run_metadata=run_metadata,
            use_on_demand_clusters=False,
        )
    assert len(caplog.records) == 1
    assert "no computational dag defined" in caplog.records[0].message
    await _assert_comp_runs_empty(sqlalchemy_async_engine)
    scheduler_rabbit_client_parser.assert_not_called()


@pytest.fixture
def with_fast_scheduling(mocker: MockerFixture) -> None:
    from simcore_service_director_v2.modules.comp_scheduler import (
        _distributed_scheduler,
    )

    mocker.patch.object(
        _distributed_scheduler, "SCHEDULER_INTERVAL", datetime.timedelta(seconds=0.01)
    )


@pytest.fixture
def mocked_schedule_pipelines(mocker: MockerFixture) -> mock.Mock:
    return mocker.patch(
        "simcore_service_director_v2.modules.comp_scheduler._distributed_scheduler.schedule_pipelines",
        autospec=True,
    )


async def test_auto_scheduling(
    with_fast_scheduling: None,
    with_disabled_scheduler_worker: mock.Mock,
    mocked_schedule_pipelines: mock.Mock,
    initialized_app: FastAPI,
    sqlalchemy_async_engine: AsyncEngine,
):
    await _assert_comp_runs_empty(sqlalchemy_async_engine)
    mocked_schedule_pipelines.assert_called()
