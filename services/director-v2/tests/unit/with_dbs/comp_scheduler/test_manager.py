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
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any
from unittest import mock

import pytest
from _helpers import PublishedProject, assert_comp_runs, assert_comp_runs_empty
from fastapi import FastAPI
from models_library.clusters import DEFAULT_CLUSTER_ID
from models_library.projects import ProjectAtDB
from models_library.projects_state import RunningState
from pytest_mock.plugin import MockerFixture
from servicelib.rabbitmq._client import RabbitMQClient
from servicelib.redis import CouldNotAcquireLockError
from servicelib.utils import limited_gather
from simcore_service_director_v2.core.errors import PipelineNotFoundError
from simcore_service_director_v2.models.comp_pipelines import CompPipelineAtDB
from simcore_service_director_v2.models.comp_runs import RunMetadataDict
from simcore_service_director_v2.modules.comp_scheduler._manager import (
    _LOST_TASKS_FACTOR,
    SCHEDULER_INTERVAL,
    run_new_pipeline,
    schedule_all_pipelines,
    stop_pipeline,
)
from simcore_service_director_v2.modules.comp_scheduler._models import (
    SchedulePipelineRabbitMessage,
)
from simcore_service_director_v2.modules.db.repositories.comp_runs import (
    CompRunsRepository,
)
from sqlalchemy.ext.asyncio import AsyncEngine

pytest_simcore_core_services_selection = ["postgres", "rabbit", "redis"]
pytest_simcore_ops_services_selection = ["adminer", "redis-commander"]


@pytest.fixture
async def scheduler_rabbit_client_parser(
    create_rabbitmq_client: Callable[[str], RabbitMQClient], mocker: MockerFixture
) -> AsyncIterator[mock.AsyncMock]:
    client = create_rabbitmq_client("scheduling_pytest_consumer")
    mock = mocker.AsyncMock(return_value=True)
    queue_name, _ = await client.subscribe(
        SchedulePipelineRabbitMessage.get_channel_name(), mock, exclusive_queue=False
    )
    yield mock
    await client.unsubscribe(queue_name)


@pytest.fixture
def with_fast_scheduling(mocker: MockerFixture) -> None:
    from simcore_service_director_v2.modules.comp_scheduler import _manager

    mocker.patch.object(
        _manager, "SCHEDULER_INTERVAL", datetime.timedelta(seconds=0.01)
    )


@pytest.fixture
def mocked_schedule_all_pipelines(mocker: MockerFixture) -> mock.Mock:
    return mocker.patch(
        "simcore_service_director_v2.modules.comp_scheduler._manager.schedule_all_pipelines",
        autospec=True,
    )


async def test_manager_starts_and_auto_schedules_pipelines(
    with_fast_scheduling: None,
    with_disabled_scheduler_worker: mock.Mock,
    mocked_schedule_all_pipelines: mock.Mock,
    initialized_app: FastAPI,
    sqlalchemy_async_engine: AsyncEngine,
):
    await assert_comp_runs_empty(sqlalchemy_async_engine)
    mocked_schedule_all_pipelines.assert_called()


async def test_schedule_all_pipelines_empty_db(
    with_disabled_auto_scheduling: mock.Mock,
    with_disabled_scheduler_worker: mock.Mock,
    initialized_app: FastAPI,
    scheduler_rabbit_client_parser: mock.AsyncMock,
    sqlalchemy_async_engine: AsyncEngine,
):
    await assert_comp_runs_empty(sqlalchemy_async_engine)

    await schedule_all_pipelines(initialized_app)

    # check nothing was distributed
    scheduler_rabbit_client_parser.assert_not_called()

    # check comp_runs is still empty
    await assert_comp_runs_empty(sqlalchemy_async_engine)


async def test_schedule_all_pipelines_concurently_runs_exclusively_and_raises(
    with_disabled_auto_scheduling: mock.Mock,
    initialized_app: FastAPI,
    mocker: MockerFixture,
):
    CONCURRENCY = 5
    # NOTE: this ensure no flakyness as empty scheduling is very fast
    # so we slow down the limited_gather function
    original_function = limited_gather

    async def slow_limited_gather(*args, **kwargs):
        result = await original_function(*args, **kwargs)
        await asyncio.sleep(3)  # to ensure flakyness does not occur
        return result

    mock_function = mocker.patch(
        "simcore_service_director_v2.modules.comp_scheduler._manager.limited_gather",
        autospec=True,
        side_effect=slow_limited_gather,
    )

    results = await asyncio.gather(
        *(schedule_all_pipelines(initialized_app) for _ in range(CONCURRENCY)),
        return_exceptions=True,
    )

    assert results.count(None) == 1, f"Only one task should have run: {results}"
    for r in results:
        if r:
            assert isinstance(r, CouldNotAcquireLockError)
    mock_function.assert_called_once()


async def test_schedule_all_pipelines(
    with_disabled_auto_scheduling: mock.Mock,
    with_disabled_scheduler_worker: mock.Mock,
    initialized_app: FastAPI,
    published_project: PublishedProject,
    sqlalchemy_async_engine: AsyncEngine,
    aiopg_engine,
    run_metadata: RunMetadataDict,
    scheduler_rabbit_client_parser: mock.AsyncMock,
):
    await assert_comp_runs_empty(sqlalchemy_async_engine)
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
    comp_run = (await assert_comp_runs(sqlalchemy_async_engine, expected_total=1))[0]
    assert comp_run.project_uuid == published_project.project.uuid
    assert comp_run.user_id == published_project.project.prj_owner
    assert comp_run.iteration == 1
    assert comp_run.cancelled is None
    assert comp_run.cluster_id == DEFAULT_CLUSTER_ID
    assert comp_run.metadata == run_metadata
    assert comp_run.result is RunningState.PUBLISHED
    assert comp_run.scheduled is not None
    assert comp_run.processed is None
    start_schedule_time = comp_run.scheduled
    start_modified_time = comp_run.modified

    # this will now not schedule the pipeline since it was already scheduled
    await schedule_all_pipelines(initialized_app)
    scheduler_rabbit_client_parser.assert_not_called()
    comp_runs = await assert_comp_runs(sqlalchemy_async_engine, expected_total=1)
    comp_run = comp_runs[0]
    assert comp_run.scheduled
    assert comp_run.scheduled == start_schedule_time, "scheduled time changed!"
    assert comp_run.cancelled is None
    assert comp_run.modified == start_modified_time

    # to simulate that the worker did its job we will set times in the past
    await CompRunsRepository(aiopg_engine).update(
        user_id=comp_run.user_id,
        project_id=comp_run.project_uuid,
        iteration=comp_run.iteration,
        scheduled=comp_run.scheduled - 1.5 * SCHEDULER_INTERVAL,
        processed=comp_run.scheduled - 1.1 * SCHEDULER_INTERVAL,
    )

    # now we schedule a pipeline again, but we wait for the scheduler interval to pass
    # this will trigger a new schedule
    await schedule_all_pipelines(initialized_app)
    scheduler_rabbit_client_parser.assert_called_once_with(
        SchedulePipelineRabbitMessage(
            user_id=published_project.project.prj_owner,
            project_id=published_project.project.uuid,
            iteration=1,
        ).body()
    )
    scheduler_rabbit_client_parser.reset_mock()
    comp_runs = await assert_comp_runs(sqlalchemy_async_engine, expected_total=1)
    comp_run = comp_runs[0]
    assert comp_run.scheduled is not None
    assert comp_run.scheduled > start_schedule_time
    last_schedule_time = comp_run.scheduled
    assert comp_run.cancelled is None
    assert comp_run.modified > start_modified_time

    # now we stop the pipeline, which should instantly trigger a schedule
    await stop_pipeline(
        initialized_app,
        user_id=published_project.project.prj_owner,
        project_id=published_project.project.uuid,
    )
    await schedule_all_pipelines(initialized_app)
    scheduler_rabbit_client_parser.assert_called_once_with(
        SchedulePipelineRabbitMessage(
            user_id=published_project.project.prj_owner,
            project_id=published_project.project.uuid,
            iteration=1,
        ).body()
    )
    scheduler_rabbit_client_parser.reset_mock()
    comp_runs = await assert_comp_runs(sqlalchemy_async_engine, expected_total=1)
    comp_run = comp_runs[0]
    assert comp_run.scheduled is not None
    assert comp_run.scheduled > last_schedule_time
    assert comp_run.cancelled is not None


async def test_schedule_all_pipelines_logs_error_if_it_find_old_pipelines(
    with_disabled_auto_scheduling: mock.Mock,
    with_disabled_scheduler_worker: mock.Mock,
    initialized_app: FastAPI,
    published_project: PublishedProject,
    sqlalchemy_async_engine: AsyncEngine,
    aiopg_engine,
    run_metadata: RunMetadataDict,
    scheduler_rabbit_client_parser: mock.AsyncMock,
    caplog: pytest.LogCaptureFixture,
):
    await assert_comp_runs_empty(sqlalchemy_async_engine)
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
    comp_run = (await assert_comp_runs(sqlalchemy_async_engine, expected_total=1))[0]
    assert comp_run.project_uuid == published_project.project.uuid
    assert comp_run.user_id == published_project.project.prj_owner
    assert comp_run.iteration == 1
    assert comp_run.cancelled is None
    assert comp_run.cluster_id == DEFAULT_CLUSTER_ID
    assert comp_run.metadata == run_metadata
    assert comp_run.result is RunningState.PUBLISHED
    assert comp_run.scheduled is not None
    start_schedule_time = comp_run.scheduled
    start_modified_time = comp_run.modified

    # this will now not schedule the pipeline since it was already scheduled
    await schedule_all_pipelines(initialized_app)
    scheduler_rabbit_client_parser.assert_not_called()
    comp_runs = await assert_comp_runs(sqlalchemy_async_engine, expected_total=1)
    comp_run = comp_runs[0]
    assert comp_run.scheduled == start_schedule_time, "scheduled time changed!"
    assert comp_run.cancelled is None
    assert comp_run.modified == start_modified_time

    # now we artificially set the last_schedule time well in the past
    await CompRunsRepository(aiopg_engine).update(
        comp_run.user_id,
        comp_run.project_uuid,
        comp_run.iteration,
        scheduled=datetime.datetime.now(tz=datetime.UTC)
        - SCHEDULER_INTERVAL * (_LOST_TASKS_FACTOR + 1),
    )
    with caplog.at_level(logging.ERROR):
        await schedule_all_pipelines(initialized_app)
        assert (
            "found 1 lost pipelines, they will be re-scheduled now" in caplog.messages
        )
    scheduler_rabbit_client_parser.assert_called_once_with(
        SchedulePipelineRabbitMessage(
            user_id=published_project.project.prj_owner,
            project_id=published_project.project.uuid,
            iteration=1,
        ).body()
    )
    scheduler_rabbit_client_parser.reset_mock()
    comp_runs = await assert_comp_runs(sqlalchemy_async_engine, expected_total=1)
    comp_run = comp_runs[0]
    assert comp_run.scheduled is not None
    assert comp_run.scheduled > start_schedule_time
    assert comp_run.cancelled is None
    assert comp_run.modified > start_modified_time


async def test_empty_pipeline_is_not_scheduled(
    with_disabled_auto_scheduling: mock.Mock,
    with_disabled_scheduler_worker: mock.Mock,
    initialized_app: FastAPI,
    registered_user: Callable[..., dict[str, Any]],
    project: Callable[..., Awaitable[ProjectAtDB]],
    create_pipeline: Callable[..., Awaitable[CompPipelineAtDB]],
    run_metadata: RunMetadataDict,
    sqlalchemy_async_engine: AsyncEngine,
    scheduler_rabbit_client_parser: mock.AsyncMock,
    caplog: pytest.LogCaptureFixture,
):
    await assert_comp_runs_empty(sqlalchemy_async_engine)
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
    await assert_comp_runs_empty(sqlalchemy_async_engine)
    scheduler_rabbit_client_parser.assert_not_called()

    # create the empty pipeline now
    await create_pipeline(project_id=f"{empty_project.uuid}")

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
    await assert_comp_runs_empty(sqlalchemy_async_engine)
    scheduler_rabbit_client_parser.assert_not_called()
