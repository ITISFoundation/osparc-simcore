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
from collections.abc import AsyncIterator, Awaitable, Callable
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, cast
from unittest import mock

import pytest
from _helpers import (
    PublishedProject,
    RunningProject,
    assert_comp_runs,
    assert_comp_runs_empty,
    assert_comp_tasks,
)
from dask_task_models_library.container_tasks.errors import TaskCancelledError
from dask_task_models_library.container_tasks.events import TaskProgressEvent
from dask_task_models_library.container_tasks.io import TaskOutputData
from dask_task_models_library.container_tasks.protocol import TaskOwner
from faker import Faker
from fastapi.applications import FastAPI
from models_library.clusters import DEFAULT_CLUSTER_ID
from models_library.projects import ProjectAtDB, ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.projects_state import RunningState
from models_library.rabbitmq_messages import (
    InstrumentationRabbitMessage,
    RabbitResourceTrackingBaseMessage,
    RabbitResourceTrackingHeartbeatMessage,
    RabbitResourceTrackingMessages,
    RabbitResourceTrackingStartedMessage,
    RabbitResourceTrackingStoppedMessage,
)
from models_library.users import UserID
from pydantic import TypeAdapter
from pytest_mock.plugin import MockerFixture
from servicelib.rabbitmq import RabbitMQClient
from simcore_postgres_database.models.comp_runs import comp_runs
from simcore_postgres_database.models.comp_tasks import NodeClass
from simcore_service_director_v2.core.errors import (
    ClustersKeeperNotAvailableError,
    ComputationalBackendNotConnectedError,
    ComputationalBackendOnDemandNotReadyError,
    ComputationalBackendTaskNotFoundError,
    ComputationalBackendTaskResultsNotReadyError,
    ComputationalSchedulerChangedError,
    ComputationalSchedulerError,
)
from simcore_service_director_v2.models.comp_pipelines import CompPipelineAtDB
from simcore_service_director_v2.models.comp_runs import CompRunsAtDB, RunMetadataDict
from simcore_service_director_v2.models.comp_tasks import CompTaskAtDB, Image
from simcore_service_director_v2.models.dask_subsystem import DaskClientTaskState
from simcore_service_director_v2.modules.comp_scheduler._manager import (
    run_new_pipeline,
    stop_pipeline,
)
from simcore_service_director_v2.modules.comp_scheduler._scheduler_base import (
    BaseCompScheduler,
)
from simcore_service_director_v2.modules.comp_scheduler._scheduler_dask import (
    DaskScheduler,
)
from simcore_service_director_v2.modules.comp_scheduler._utils import COMPLETED_STATES
from simcore_service_director_v2.modules.comp_scheduler._worker import (
    _get_scheduler_worker,
)
from simcore_service_director_v2.modules.dask_client import (
    DaskJobID,
    PublishedComputationTask,
)
from simcore_service_director_v2.utils.dask_client_utils import TaskHandlers
from sqlalchemy import and_
from sqlalchemy.ext.asyncio import AsyncEngine
from tenacity.asyncio import AsyncRetrying
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed

pytest_simcore_core_services_selection = ["postgres", "rabbit", "redis"]
pytest_simcore_ops_services_selection = [
    "adminer",
]


def _assert_dask_client_correctly_initialized(
    mocked_dask_client: mock.MagicMock, scheduler: BaseCompScheduler
) -> None:
    mocked_dask_client.create.assert_called_once_with(
        app=mock.ANY,
        settings=mock.ANY,
        endpoint=mock.ANY,
        authentication=mock.ANY,
        tasks_file_link_type=mock.ANY,
        cluster_type=mock.ANY,
    )
    mocked_dask_client.register_handlers.assert_called_once_with(
        TaskHandlers(
            cast(  # noqa: SLF001
                DaskScheduler, scheduler
            )._task_progress_change_handler,
            cast(DaskScheduler, scheduler)._task_log_change_handler,  # noqa: SLF001
        )
    )


@pytest.fixture
def mocked_dask_client(mocker: MockerFixture) -> mock.Mock:
    mocked_dask_client = mocker.patch(
        "simcore_service_director_v2.modules.dask_clients_pool.DaskClient",
        autospec=True,
    )
    mocked_dask_client.create.return_value = mocked_dask_client
    return mocked_dask_client


@pytest.fixture
def mocked_parse_output_data_fct(mocker: MockerFixture) -> mock.Mock:
    return mocker.patch(
        "simcore_service_director_v2.modules.comp_scheduler._scheduler_dask.parse_output_data",
        autospec=True,
    )


@pytest.fixture
def mocked_clean_task_output_fct(mocker: MockerFixture) -> mock.Mock:
    return mocker.patch(
        "simcore_service_director_v2.modules.comp_scheduler._scheduler_dask.clean_task_output_and_log_files_if_invalid",
        return_value=None,
        autospec=True,
    )


@pytest.fixture
def mocked_clean_task_output_and_log_files_if_invalid(
    mocker: MockerFixture,
) -> mock.Mock:
    return mocker.patch(
        "simcore_service_director_v2.modules.comp_scheduler._scheduler_dask.clean_task_output_and_log_files_if_invalid",
        autospec=True,
    )


@pytest.fixture
def scheduler_api(initialized_app: FastAPI) -> BaseCompScheduler:
    return _get_scheduler_worker(initialized_app)


async def _assert_start_pipeline(
    app: FastAPI,
    *,
    sqlalchemy_async_engine: AsyncEngine,
    published_project: PublishedProject,
    run_metadata: RunMetadataDict,
) -> tuple[CompRunsAtDB, list[CompTaskAtDB]]:
    exp_published_tasks = deepcopy(published_project.tasks)
    assert published_project.project.prj_owner
    await run_new_pipeline(
        app,
        user_id=published_project.project.prj_owner,
        project_id=published_project.project.uuid,
        cluster_id=DEFAULT_CLUSTER_ID,
        run_metadata=run_metadata,
        use_on_demand_clusters=False,
    )

    # check the database is correctly updated, the run is published
    runs = await assert_comp_runs(
        sqlalchemy_async_engine,
        expected_total=1,
        expected_state=RunningState.PUBLISHED,
        where_statement=and_(
            comp_runs.c.user_id == published_project.project.prj_owner,
            comp_runs.c.project_uuid == f"{published_project.project.uuid}",
        ),
    )
    await assert_comp_tasks(
        sqlalchemy_async_engine,
        project_uuid=published_project.project.uuid,
        task_ids=[p.node_id for p in exp_published_tasks],
        expected_state=RunningState.PUBLISHED,
        expected_progress=None,
    )
    return runs[0], exp_published_tasks


async def _assert_publish_in_dask_backend(
    sqlalchemy_async_engine: AsyncEngine,
    published_project: PublishedProject,
    published_tasks: list[CompTaskAtDB],
    mocked_dask_client: mock.MagicMock,
    scheduler: BaseCompScheduler,
) -> tuple[list[CompTaskAtDB], dict[NodeID, Callable[[], None]]]:
    expected_pending_tasks = [
        published_tasks[1],
        published_tasks[3],
    ]
    for p in expected_pending_tasks:
        published_tasks.remove(p)

    async def _return_tasks_pending(job_ids: list[str]) -> list[DaskClientTaskState]:
        return [DaskClientTaskState.PENDING for job_id in job_ids]

    mocked_dask_client.get_tasks_status.side_effect = _return_tasks_pending
    assert published_project.project.prj_owner
    await scheduler.apply(
        user_id=published_project.project.prj_owner,
        project_id=published_project.project.uuid,
        iteration=1,
    )
    _assert_dask_client_correctly_initialized(mocked_dask_client, scheduler)
    await assert_comp_runs(
        sqlalchemy_async_engine,
        expected_total=1,
        expected_state=RunningState.PUBLISHED,
        where_statement=and_(
            comp_runs.c.user_id == published_project.project.prj_owner,
            comp_runs.c.project_uuid == f"{published_project.project.uuid}",
        ),
    )
    await assert_comp_tasks(
        sqlalchemy_async_engine,
        project_uuid=published_project.project.uuid,
        task_ids=[p.node_id for p in expected_pending_tasks],
        expected_state=RunningState.PENDING,
        expected_progress=None,
    )
    # the other tasks are still waiting in published state
    await assert_comp_tasks(
        sqlalchemy_async_engine,
        project_uuid=published_project.project.uuid,
        task_ids=[p.node_id for p in published_tasks],
        expected_state=RunningState.PUBLISHED,
        expected_progress=None,  # since we bypass the API entrypoint this is correct
    )
    # tasks were send to the backend
    assert published_project.project.prj_owner is not None
    assert isinstance(mocked_dask_client.send_computation_tasks, mock.Mock)
    assert isinstance(mocked_dask_client.get_tasks_status, mock.Mock)
    assert isinstance(mocked_dask_client.get_task_result, mock.Mock)
    mocked_dask_client.send_computation_tasks.assert_has_calls(
        calls=[
            mock.call(
                user_id=published_project.project.prj_owner,
                project_id=published_project.project.uuid,
                cluster_id=DEFAULT_CLUSTER_ID,
                tasks={f"{p.node_id}": p.image},
                callback=mock.ANY,
                metadata=mock.ANY,
                hardware_info=mock.ANY,
            )
            for p in expected_pending_tasks
        ],
        any_order=True,
    )
    task_to_callback_mapping = {
        task.node_id: mocked_dask_client.send_computation_tasks.call_args_list[
            i
        ].kwargs["callback"]
        for i, task in enumerate(expected_pending_tasks)
    }
    mocked_dask_client.send_computation_tasks.reset_mock()
    mocked_dask_client.get_tasks_status.assert_not_called()
    mocked_dask_client.get_task_result.assert_not_called()
    # there is a second run of the scheduler to move comp_runs to pending, the rest does not change
    await scheduler.apply(
        user_id=published_project.project.prj_owner,
        project_id=published_project.project.uuid,
        iteration=1,
    )
    await assert_comp_runs(
        sqlalchemy_async_engine,
        expected_total=1,
        expected_state=RunningState.PENDING,
        where_statement=(comp_runs.c.user_id == published_project.project.prj_owner)
        & (comp_runs.c.project_uuid == f"{published_project.project.uuid}"),
    )
    await assert_comp_tasks(
        sqlalchemy_async_engine,
        project_uuid=published_project.project.uuid,
        task_ids=[p.node_id for p in expected_pending_tasks],
        expected_state=RunningState.PENDING,
        expected_progress=None,
    )
    await assert_comp_tasks(
        sqlalchemy_async_engine,
        project_uuid=published_project.project.uuid,
        task_ids=[p.node_id for p in published_tasks],
        expected_state=RunningState.PUBLISHED,
        expected_progress=None,
    )
    mocked_dask_client.send_computation_tasks.assert_not_called()
    mocked_dask_client.get_tasks_status.assert_has_calls(
        calls=[mock.call([p.job_id for p in expected_pending_tasks])], any_order=True
    )
    mocked_dask_client.get_tasks_status.reset_mock()
    mocked_dask_client.get_task_result.assert_not_called()
    return expected_pending_tasks, task_to_callback_mapping


@pytest.fixture
async def instrumentation_rabbit_client_parser(
    create_rabbitmq_client: Callable[[str], RabbitMQClient], mocker: MockerFixture
) -> AsyncIterator[mock.AsyncMock]:
    client = create_rabbitmq_client("instrumentation_pytest_consumer")
    mock = mocker.AsyncMock(return_value=True)
    queue_name, _ = await client.subscribe(
        InstrumentationRabbitMessage.get_channel_name(), mock
    )
    yield mock
    await client.unsubscribe(queue_name)


@pytest.fixture
async def resource_tracking_rabbit_client_parser(
    create_rabbitmq_client: Callable[[str], RabbitMQClient], mocker: MockerFixture
) -> AsyncIterator[mock.AsyncMock]:
    client = create_rabbitmq_client("resource_tracking_pytest_consumer")
    mock = mocker.AsyncMock(return_value=True)
    queue_name, _ = await client.subscribe(
        RabbitResourceTrackingBaseMessage.get_channel_name(), mock
    )
    yield mock
    await client.unsubscribe(queue_name)


async def _assert_message_received(
    mocked_message_parser: mock.AsyncMock,
    expected_call_count: int,
    message_parser: Callable,
) -> list:
    async for attempt in AsyncRetrying(
        wait=wait_fixed(0.1),
        stop=stop_after_delay(5),
        retry=retry_if_exception_type(AssertionError),
        reraise=True,
    ):
        with attempt:
            print(
                f"--> waiting for rabbitmq message [{attempt.retry_state.attempt_number}, {attempt.retry_state.idle_for}]"
            )
            assert mocked_message_parser.call_count == expected_call_count
            print(
                f"<-- rabbitmq message received after [{attempt.retry_state.attempt_number}, {attempt.retry_state.idle_for}]"
            )
    parsed_messages = [
        message_parser(mocked_message_parser.call_args_list[c].args[0])
        for c in range(expected_call_count)
    ]

    mocked_message_parser.reset_mock()
    return parsed_messages


def _with_mock_send_computation_tasks(
    tasks: list[CompTaskAtDB], mocked_dask_client: mock.MagicMock
) -> mock.Mock:
    node_id_to_job_id_map = {task.node_id: task.job_id for task in tasks}

    async def _send_computation_tasks(
        *args, tasks: dict[NodeID, Image], **kwargs
    ) -> list[PublishedComputationTask]:
        for node_id in tasks:
            assert NodeID(f"{node_id}") in node_id_to_job_id_map
        return [
            PublishedComputationTask(
                node_id=NodeID(f"{node_id}"),
                job_id=DaskJobID(node_id_to_job_id_map[NodeID(f"{node_id}")]),
            )
            for node_id in tasks
        ]  # type: ignore

    mocked_dask_client.send_computation_tasks.side_effect = _send_computation_tasks
    return mocked_dask_client.send_computation_tasks


async def _trigger_progress_event(
    scheduler: BaseCompScheduler,
    *,
    job_id: str,
    user_id: UserID,
    project_id: ProjectID,
    node_id: NodeID,
) -> None:
    event = TaskProgressEvent(
        job_id=job_id,
        progress=0,
        task_owner=TaskOwner(
            user_id=user_id,
            project_id=project_id,
            node_id=node_id,
            parent_project_id=None,
            parent_node_id=None,
        ),
    )
    await cast(DaskScheduler, scheduler)._task_progress_change_handler(  # noqa: SLF001
        event.model_dump_json()
    )


@pytest.mark.acceptance_test()
async def test_proper_pipeline_is_scheduled(  # noqa: PLR0915
    with_disabled_auto_scheduling: mock.Mock,
    with_disabled_scheduler_publisher: mock.Mock,
    initialized_app: FastAPI,
    mocked_dask_client: mock.MagicMock,
    scheduler_api: BaseCompScheduler,
    sqlalchemy_async_engine: AsyncEngine,
    published_project: PublishedProject,
    mocked_parse_output_data_fct: mock.Mock,
    mocked_clean_task_output_and_log_files_if_invalid: mock.Mock,
    instrumentation_rabbit_client_parser: mock.AsyncMock,
    resource_tracking_rabbit_client_parser: mock.AsyncMock,
    run_metadata: RunMetadataDict,
):
    with_disabled_auto_scheduling.assert_called_once()
    _with_mock_send_computation_tasks(published_project.tasks, mocked_dask_client)

    #
    # Initiate new pipeline run
    #
    run_in_db, expected_published_tasks = await _assert_start_pipeline(
        initialized_app,
        sqlalchemy_async_engine=sqlalchemy_async_engine,
        published_project=published_project,
        run_metadata=run_metadata,
    )
    with_disabled_scheduler_publisher.assert_called()

    # -------------------------------------------------------------------------------
    # 1. first run will move comp_tasks to PENDING so the dask-worker can take them
    expected_pending_tasks, _ = await _assert_publish_in_dask_backend(
        sqlalchemy_async_engine,
        published_project,
        expected_published_tasks,
        mocked_dask_client,
        scheduler_api,
    )

    # -------------------------------------------------------------------------------
    # 2.1. the dask-worker might be taking the task, until we get a progress we do not know
    #      whether it effectively started or it is still queued in the worker process
    exp_started_task = expected_pending_tasks[0]
    expected_pending_tasks.remove(exp_started_task)

    async def _return_1st_task_running(job_ids: list[str]) -> list[DaskClientTaskState]:
        return [
            (
                DaskClientTaskState.PENDING_OR_STARTED
                if job_id == exp_started_task.job_id
                else DaskClientTaskState.PENDING
            )
            for job_id in job_ids
        ]

    mocked_dask_client.get_tasks_status.side_effect = _return_1st_task_running
    await scheduler_api.apply(
        user_id=run_in_db.user_id,
        project_id=run_in_db.project_uuid,
        iteration=run_in_db.iteration,
    )
    await assert_comp_runs(
        sqlalchemy_async_engine,
        expected_total=1,
        expected_state=RunningState.PENDING,
        where_statement=and_(
            comp_runs.c.user_id == published_project.project.prj_owner,
            comp_runs.c.project_uuid == f"{published_project.project.uuid}",
        ),
    )
    await assert_comp_tasks(
        sqlalchemy_async_engine,
        project_uuid=published_project.project.uuid,
        task_ids=[exp_started_task.node_id]
        + [p.node_id for p in expected_pending_tasks],
        expected_state=RunningState.PENDING,
        expected_progress=None,
    )
    await assert_comp_tasks(
        sqlalchemy_async_engine,
        project_uuid=published_project.project.uuid,
        task_ids=[p.node_id for p in expected_published_tasks],
        expected_state=RunningState.PUBLISHED,
        expected_progress=None,  # since we bypass the API entrypoint this is correct
    )
    mocked_dask_client.send_computation_tasks.assert_not_called()
    mocked_dask_client.get_tasks_status.assert_called_once_with(
        [p.job_id for p in (exp_started_task, *expected_pending_tasks)],
    )
    mocked_dask_client.get_tasks_status.reset_mock()
    mocked_dask_client.get_task_result.assert_not_called()

    # -------------------------------------------------------------------------------
    # 3. the dask-worker starts processing a task here we simulate a progress event
    assert exp_started_task.job_id
    assert exp_started_task.project_id
    assert exp_started_task.node_id
    assert published_project.project.prj_owner
    await _trigger_progress_event(
        scheduler_api,
        job_id=exp_started_task.job_id,
        user_id=published_project.project.prj_owner,
        project_id=exp_started_task.project_id,
        node_id=exp_started_task.node_id,
    )

    await scheduler_api.apply(
        user_id=run_in_db.user_id,
        project_id=run_in_db.project_uuid,
        iteration=run_in_db.iteration,
    )
    # comp_run, the comp_task switch to STARTED
    await assert_comp_runs(
        sqlalchemy_async_engine,
        expected_total=1,
        expected_state=RunningState.STARTED,
        where_statement=and_(
            comp_runs.c.user_id == published_project.project.prj_owner,
            comp_runs.c.project_uuid == f"{published_project.project.uuid}",
        ),
    )
    await assert_comp_tasks(
        sqlalchemy_async_engine,
        project_uuid=published_project.project.uuid,
        task_ids=[exp_started_task.node_id],
        expected_state=RunningState.STARTED,
        expected_progress=0,
    )
    await assert_comp_tasks(
        sqlalchemy_async_engine,
        project_uuid=published_project.project.uuid,
        task_ids=[p.node_id for p in expected_pending_tasks],
        expected_state=RunningState.PENDING,
        expected_progress=None,
    )
    await assert_comp_tasks(
        sqlalchemy_async_engine,
        project_uuid=published_project.project.uuid,
        task_ids=[p.node_id for p in expected_published_tasks],
        expected_state=RunningState.PUBLISHED,
        expected_progress=None,
    )
    mocked_dask_client.send_computation_tasks.assert_not_called()
    mocked_dask_client.get_tasks_status.assert_called_once_with(
        [p.job_id for p in (exp_started_task, *expected_pending_tasks)],
    )
    mocked_dask_client.get_tasks_status.reset_mock()
    mocked_dask_client.get_task_result.assert_not_called()
    # check the metrics are properly published
    messages = await _assert_message_received(
        instrumentation_rabbit_client_parser,
        1,
        InstrumentationRabbitMessage.model_validate_json,
    )
    assert messages[0].metrics == "service_started"
    assert messages[0].service_uuid == exp_started_task.node_id

    # check the RUT messages are properly published
    messages = await _assert_message_received(
        resource_tracking_rabbit_client_parser,
        1,
        RabbitResourceTrackingStartedMessage.model_validate_json,
    )
    assert messages[0].node_id == exp_started_task.node_id

    # -------------------------------------------------------------------------------
    # 4. the dask-worker completed the task successfully
    async def _return_1st_task_success(job_ids: list[str]) -> list[DaskClientTaskState]:
        return [
            (
                DaskClientTaskState.SUCCESS
                if job_id == exp_started_task.job_id
                else DaskClientTaskState.PENDING
            )
            for job_id in job_ids
        ]

    mocked_dask_client.get_tasks_status.side_effect = _return_1st_task_success

    async def _return_random_task_result(job_id) -> TaskOutputData:
        return TaskOutputData.model_validate({"out_1": None, "out_2": 45})

    mocked_dask_client.get_task_result.side_effect = _return_random_task_result
    await scheduler_api.apply(
        user_id=run_in_db.user_id,
        project_id=run_in_db.project_uuid,
        iteration=run_in_db.iteration,
    )
    await assert_comp_runs(
        sqlalchemy_async_engine,
        expected_total=1,
        expected_state=RunningState.STARTED,
        where_statement=and_(
            comp_runs.c.user_id == published_project.project.prj_owner,
            comp_runs.c.project_uuid == f"{published_project.project.uuid}",
        ),
    )
    await assert_comp_tasks(
        sqlalchemy_async_engine,
        project_uuid=published_project.project.uuid,
        task_ids=[exp_started_task.node_id],
        expected_state=RunningState.SUCCESS,
        expected_progress=1,
    )
    # check metrics are published
    messages = await _assert_message_received(
        instrumentation_rabbit_client_parser,
        1,
        InstrumentationRabbitMessage.model_validate_json,
    )
    assert messages[0].metrics == "service_stopped"
    assert messages[0].service_uuid == exp_started_task.node_id
    # check RUT messages are published
    messages = await _assert_message_received(
        resource_tracking_rabbit_client_parser,
        1,
        RabbitResourceTrackingStoppedMessage.model_validate_json,
    )

    completed_tasks = [exp_started_task]
    next_pending_task = published_project.tasks[2]
    expected_pending_tasks.append(next_pending_task)
    await assert_comp_tasks(
        sqlalchemy_async_engine,
        project_uuid=published_project.project.uuid,
        task_ids=[p.node_id for p in expected_pending_tasks],
        expected_state=RunningState.PENDING,
        expected_progress=None,
    )
    await assert_comp_tasks(
        sqlalchemy_async_engine,
        project_uuid=published_project.project.uuid,
        task_ids=[
            p.node_id
            for p in published_project.tasks
            if p not in expected_pending_tasks + completed_tasks
        ],
        expected_state=RunningState.PUBLISHED,
        expected_progress=None,  # since we bypass the API entrypoint this is correct
    )
    mocked_dask_client.send_computation_tasks.assert_called_once_with(
        user_id=published_project.project.prj_owner,
        project_id=published_project.project.uuid,
        cluster_id=DEFAULT_CLUSTER_ID,
        tasks={
            f"{next_pending_task.node_id}": next_pending_task.image,
        },
        callback=mock.ANY,
        metadata=mock.ANY,
        hardware_info=mock.ANY,
    )
    mocked_dask_client.send_computation_tasks.reset_mock()
    mocked_dask_client.get_tasks_status.assert_has_calls(
        calls=[
            mock.call([p.job_id for p in completed_tasks + expected_pending_tasks[:1]])
        ],
        any_order=True,
    )
    mocked_dask_client.get_tasks_status.reset_mock()
    mocked_dask_client.get_task_result.assert_called_once_with(
        completed_tasks[0].job_id
    )
    mocked_dask_client.get_task_result.reset_mock()
    mocked_parse_output_data_fct.assert_called_once_with(
        mock.ANY,
        completed_tasks[0].job_id,
        await _return_random_task_result(completed_tasks[0].job_id),
    )
    mocked_parse_output_data_fct.reset_mock()

    # -------------------------------------------------------------------------------
    # 6. the dask-worker starts processing a task
    exp_started_task = next_pending_task

    async def _return_2nd_task_running(job_ids: list[str]) -> list[DaskClientTaskState]:
        return [
            (
                DaskClientTaskState.PENDING_OR_STARTED
                if job_id == exp_started_task.job_id
                else DaskClientTaskState.PENDING
            )
            for job_id in job_ids
        ]

    mocked_dask_client.get_tasks_status.side_effect = _return_2nd_task_running
    # trigger the scheduler, run state should keep to STARTED, task should be as well
    assert exp_started_task.job_id
    await _trigger_progress_event(
        scheduler_api,
        job_id=exp_started_task.job_id,
        user_id=published_project.project.prj_owner,
        project_id=exp_started_task.project_id,
        node_id=exp_started_task.node_id,
    )
    await scheduler_api.apply(
        user_id=run_in_db.user_id,
        project_id=run_in_db.project_uuid,
        iteration=run_in_db.iteration,
    )
    await assert_comp_runs(
        sqlalchemy_async_engine,
        expected_total=1,
        expected_state=RunningState.STARTED,
        where_statement=and_(
            comp_runs.c.user_id == published_project.project.prj_owner,
            comp_runs.c.project_uuid == f"{published_project.project.uuid}",
        ),
    )
    await assert_comp_tasks(
        sqlalchemy_async_engine,
        project_uuid=published_project.project.uuid,
        task_ids=[exp_started_task.node_id],
        expected_state=RunningState.STARTED,
        expected_progress=0,
    )
    mocked_dask_client.send_computation_tasks.assert_not_called()
    expected_pending_tasks.reverse()
    mocked_dask_client.get_tasks_status.assert_called_once_with(
        [p.job_id for p in expected_pending_tasks]
    )
    mocked_dask_client.get_tasks_status.reset_mock()
    mocked_dask_client.get_task_result.assert_not_called()
    messages = await _assert_message_received(
        instrumentation_rabbit_client_parser,
        1,
        InstrumentationRabbitMessage.model_validate_json,
    )
    assert messages[0].metrics == "service_started"
    assert messages[0].service_uuid == exp_started_task.node_id
    messages = await _assert_message_received(
        resource_tracking_rabbit_client_parser,
        1,
        RabbitResourceTrackingStartedMessage.model_validate_json,
    )
    assert messages[0].node_id == exp_started_task.node_id

    # -------------------------------------------------------------------------------
    # 7. the task fails
    async def _return_2nd_task_failed(job_ids: list[str]) -> list[DaskClientTaskState]:
        return [
            (
                DaskClientTaskState.ERRED
                if job_id == exp_started_task.job_id
                else DaskClientTaskState.PENDING
            )
            for job_id in job_ids
        ]

    mocked_dask_client.get_tasks_status.side_effect = _return_2nd_task_failed
    mocked_dask_client.get_task_result.side_effect = None
    await scheduler_api.apply(
        user_id=run_in_db.user_id,
        project_id=run_in_db.project_uuid,
        iteration=run_in_db.iteration,
    )
    mocked_clean_task_output_and_log_files_if_invalid.assert_called_once()
    mocked_clean_task_output_and_log_files_if_invalid.reset_mock()

    await assert_comp_runs(
        sqlalchemy_async_engine,
        expected_total=1,
        expected_state=RunningState.STARTED,
        where_statement=and_(
            comp_runs.c.user_id == published_project.project.prj_owner,
            comp_runs.c.project_uuid == f"{published_project.project.uuid}",
        ),
    )
    await assert_comp_tasks(
        sqlalchemy_async_engine,
        project_uuid=published_project.project.uuid,
        task_ids=[exp_started_task.node_id],
        expected_state=RunningState.FAILED,
        expected_progress=1,
    )
    mocked_dask_client.send_computation_tasks.assert_not_called()
    mocked_dask_client.get_tasks_status.assert_called_once_with(
        [p.job_id for p in expected_pending_tasks]
    )
    mocked_dask_client.get_tasks_status.reset_mock()
    mocked_dask_client.get_task_result.assert_called_once_with(exp_started_task.job_id)
    mocked_dask_client.get_task_result.reset_mock()
    mocked_parse_output_data_fct.assert_not_called()
    expected_pending_tasks.remove(exp_started_task)
    messages = await _assert_message_received(
        instrumentation_rabbit_client_parser,
        1,
        InstrumentationRabbitMessage.model_validate_json,
    )
    assert messages[0].metrics == "service_stopped"
    assert messages[0].service_uuid == exp_started_task.node_id
    messages = await _assert_message_received(
        resource_tracking_rabbit_client_parser,
        1,
        RabbitResourceTrackingStoppedMessage.model_validate_json,
    )

    # -------------------------------------------------------------------------------
    # 8. the last task shall succeed
    exp_started_task = expected_pending_tasks[0]

    async def _return_3rd_task_success(job_ids: list[str]) -> list[DaskClientTaskState]:
        return [
            (
                DaskClientTaskState.SUCCESS
                if job_id == exp_started_task.job_id
                else DaskClientTaskState.PENDING
            )
            for job_id in job_ids
        ]

    mocked_dask_client.get_tasks_status.side_effect = _return_3rd_task_success
    mocked_dask_client.get_task_result.side_effect = _return_random_task_result

    # trigger the scheduler, it should switch to FAILED, as we are done
    await scheduler_api.apply(
        user_id=run_in_db.user_id,
        project_id=run_in_db.project_uuid,
        iteration=run_in_db.iteration,
    )
    mocked_clean_task_output_and_log_files_if_invalid.assert_not_called()
    await assert_comp_runs(
        sqlalchemy_async_engine,
        expected_total=1,
        expected_state=RunningState.FAILED,
        where_statement=and_(
            comp_runs.c.user_id == published_project.project.prj_owner,
            comp_runs.c.project_uuid == f"{published_project.project.uuid}",
        ),
    )

    await assert_comp_tasks(
        sqlalchemy_async_engine,
        project_uuid=published_project.project.uuid,
        task_ids=[exp_started_task.node_id],
        expected_state=RunningState.SUCCESS,
        expected_progress=1,
    )
    mocked_dask_client.send_computation_tasks.assert_not_called()
    mocked_dask_client.get_tasks_status.assert_called_once_with(
        [p.job_id for p in expected_pending_tasks]
    )
    mocked_dask_client.get_task_result.assert_called_once_with(exp_started_task.job_id)
    messages = await _assert_message_received(
        instrumentation_rabbit_client_parser,
        2,
        InstrumentationRabbitMessage.model_validate_json,
    )

    # NOTE: the service was fast and went directly to success
    def _parser(x) -> RabbitResourceTrackingMessages:
        return TypeAdapter(RabbitResourceTrackingMessages).validate_json(x)

    assert messages[0].metrics == "service_started"
    assert messages[0].service_uuid == exp_started_task.node_id
    assert messages[1].metrics == "service_stopped"
    assert messages[1].service_uuid == exp_started_task.node_id
    messages = await _assert_message_received(
        resource_tracking_rabbit_client_parser,
        2,
        _parser,
    )
    assert isinstance(messages[0], RabbitResourceTrackingStartedMessage)
    assert isinstance(messages[1], RabbitResourceTrackingStoppedMessage)


@pytest.fixture
async def with_started_project(
    with_disabled_auto_scheduling: mock.Mock,
    with_disabled_scheduler_publisher: mock.Mock,
    initialized_app: FastAPI,
    sqlalchemy_async_engine: AsyncEngine,
    publish_project: Callable[[], Awaitable[PublishedProject]],
    mocked_dask_client: mock.Mock,
    run_metadata: RunMetadataDict,
    scheduler_api: BaseCompScheduler,
    instrumentation_rabbit_client_parser: mock.AsyncMock,
    resource_tracking_rabbit_client_parser: mock.AsyncMock,
) -> RunningProject:
    with_disabled_auto_scheduling.assert_called_once()
    published_project = await publish_project()
    #
    # 1. Initiate new pipeline run
    #
    run_in_db, expected_published_tasks = await _assert_start_pipeline(
        initialized_app,
        sqlalchemy_async_engine=sqlalchemy_async_engine,
        published_project=published_project,
        run_metadata=run_metadata,
    )
    with_disabled_scheduler_publisher.assert_called_once()

    #
    # 2. This runs the scheduler until the project is started scheduled in the back-end
    #
    (
        expected_pending_tasks,
        task_to_callback_mapping,
    ) = await _assert_publish_in_dask_backend(
        sqlalchemy_async_engine,
        published_project,
        expected_published_tasks,
        mocked_dask_client,
        scheduler_api,
    )

    #
    # The dask-worker can take a job when it is PENDING, but the dask scheduler makes
    # no difference between PENDING and STARTED
    #
    exp_started_task = expected_pending_tasks[0]
    expected_pending_tasks.remove(exp_started_task)

    async def _return_1st_task_running(job_ids: list[str]) -> list[DaskClientTaskState]:
        return [
            (
                DaskClientTaskState.PENDING_OR_STARTED
                if job_id == exp_started_task.job_id
                else DaskClientTaskState.PENDING
            )
            for job_id in job_ids
        ]

    assert isinstance(mocked_dask_client.get_tasks_status, mock.Mock)
    assert isinstance(mocked_dask_client.send_computation_tasks, mock.Mock)
    assert isinstance(mocked_dask_client.get_task_result, mock.Mock)
    mocked_dask_client.get_tasks_status.side_effect = _return_1st_task_running
    await scheduler_api.apply(
        user_id=run_in_db.user_id,
        project_id=run_in_db.project_uuid,
        iteration=run_in_db.iteration,
    )
    await assert_comp_runs(
        sqlalchemy_async_engine,
        expected_total=1,
        expected_state=RunningState.PENDING,
        where_statement=and_(
            comp_runs.c.user_id == published_project.project.prj_owner,
            comp_runs.c.project_uuid == f"{published_project.project.uuid}",
        ),
    )
    await assert_comp_tasks(
        sqlalchemy_async_engine,
        project_uuid=published_project.project.uuid,
        task_ids=[exp_started_task.node_id]
        + [p.node_id for p in expected_pending_tasks],
        expected_state=RunningState.PENDING,
        expected_progress=None,
    )
    await assert_comp_tasks(
        sqlalchemy_async_engine,
        project_uuid=published_project.project.uuid,
        task_ids=[p.node_id for p in expected_published_tasks],
        expected_state=RunningState.PUBLISHED,
        expected_progress=None,  # since we bypass the API entrypoint this is correct
    )
    mocked_dask_client.send_computation_tasks.assert_not_called()
    mocked_dask_client.get_tasks_status.assert_called_once_with(
        [p.job_id for p in (exp_started_task, *expected_pending_tasks)],
    )
    mocked_dask_client.get_tasks_status.reset_mock()
    mocked_dask_client.get_task_result.assert_not_called()

    # -------------------------------------------------------------------------------
    # 4. the dask-worker starts processing a task here we simulate a progress event
    assert exp_started_task.job_id
    assert exp_started_task.project_id
    assert exp_started_task.node_id
    assert published_project.project.prj_owner
    await _trigger_progress_event(
        scheduler_api,
        job_id=exp_started_task.job_id,
        user_id=published_project.project.prj_owner,
        project_id=exp_started_task.project_id,
        node_id=exp_started_task.node_id,
    )

    await scheduler_api.apply(
        user_id=run_in_db.user_id,
        project_id=run_in_db.project_uuid,
        iteration=run_in_db.iteration,
    )
    # comp_run, the comp_task switch to STARTED
    run_in_db = (
        await assert_comp_runs(
            sqlalchemy_async_engine,
            expected_total=1,
            expected_state=RunningState.STARTED,
            where_statement=and_(
                comp_runs.c.user_id == published_project.project.prj_owner,
                comp_runs.c.project_uuid == f"{published_project.project.uuid}",
            ),
        )
    )[0]
    tasks_in_db = await assert_comp_tasks(
        sqlalchemy_async_engine,
        project_uuid=published_project.project.uuid,
        task_ids=[exp_started_task.node_id],
        expected_state=RunningState.STARTED,
        expected_progress=0,
    )
    tasks_in_db += await assert_comp_tasks(
        sqlalchemy_async_engine,
        project_uuid=published_project.project.uuid,
        task_ids=[p.node_id for p in expected_pending_tasks],
        expected_state=RunningState.PENDING,
        expected_progress=None,
    )
    tasks_in_db += await assert_comp_tasks(
        sqlalchemy_async_engine,
        project_uuid=published_project.project.uuid,
        task_ids=[p.node_id for p in expected_published_tasks],
        expected_state=RunningState.PUBLISHED,
        expected_progress=None,
    )
    mocked_dask_client.send_computation_tasks.assert_not_called()
    mocked_dask_client.get_tasks_status.assert_called_once_with(
        [p.job_id for p in (exp_started_task, *expected_pending_tasks)],
    )
    mocked_dask_client.get_tasks_status.reset_mock()
    mocked_dask_client.get_task_result.assert_not_called()
    # check the metrics are properly published
    messages = await _assert_message_received(
        instrumentation_rabbit_client_parser,
        1,
        InstrumentationRabbitMessage.model_validate_json,
    )
    assert messages[0].metrics == "service_started"
    assert messages[0].service_uuid == exp_started_task.node_id

    # check the RUT messages are properly published
    messages = await _assert_message_received(
        resource_tracking_rabbit_client_parser,
        1,
        RabbitResourceTrackingStartedMessage.model_validate_json,
    )
    assert messages[0].node_id == exp_started_task.node_id

    return RunningProject(
        published_project.user,
        published_project.project,
        published_project.pipeline,
        tasks_in_db,
        runs=run_in_db,
        task_to_callback_mapping=task_to_callback_mapping,
    )


@pytest.fixture
def mocked_worker_publisher(mocker: MockerFixture) -> mock.Mock:
    return mocker.patch(
        "simcore_service_director_v2.modules.comp_scheduler._scheduler_base.request_pipeline_scheduling",
        autospec=True,
    )


async def test_completed_task_triggers_new_scheduling_task(
    mocked_worker_publisher: mock.Mock,
    with_started_project: RunningProject,
):
    """When a pipeline job completes, the Dask backend provides a callback
    that runs in a separate thread. We use that callback to ask the
    director-v2 computational scheduler manager to ask for a new schedule
    After fiddling in distributed source code, here is a similar way to trigger that callback
    """
    completed_node_id = with_started_project.tasks[0].node_id
    callback = with_started_project.task_to_callback_mapping[completed_node_id]
    await asyncio.to_thread(callback)

    mocked_worker_publisher.assert_called_once_with(
        mock.ANY,
        mock.ANY,
        user_id=with_started_project.runs.user_id,
        project_id=with_started_project.runs.project_uuid,
        iteration=with_started_project.runs.iteration,
    )


async def test_broken_pipeline_configuration_is_not_scheduled_and_aborted(
    with_disabled_auto_scheduling: mock.Mock,
    with_disabled_scheduler_publisher: mock.Mock,
    initialized_app: FastAPI,
    scheduler_api: BaseCompScheduler,
    registered_user: Callable[..., dict[str, Any]],
    project: Callable[..., Awaitable[ProjectAtDB]],
    create_pipeline: Callable[..., Awaitable[CompPipelineAtDB]],
    fake_workbench_without_outputs: dict[str, Any],
    fake_workbench_adjacency: dict[str, Any],
    sqlalchemy_async_engine: AsyncEngine,
    run_metadata: RunMetadataDict,
):
    """A pipeline which comp_tasks are missing should not be scheduled.
    It shall be aborted and shown as such in the comp_runs db"""
    user = registered_user()
    sleepers_project = await project(user, workbench=fake_workbench_without_outputs)
    await create_pipeline(
        project_id=f"{sleepers_project.uuid}",
        dag_adjacency_list=fake_workbench_adjacency,
    )
    await assert_comp_runs_empty(sqlalchemy_async_engine)

    #
    # Initiate new pipeline scheduling
    #
    await run_new_pipeline(
        initialized_app,
        user_id=user["id"],
        project_id=sleepers_project.uuid,
        cluster_id=DEFAULT_CLUSTER_ID,
        run_metadata=run_metadata,
        use_on_demand_clusters=False,
    )
    with_disabled_scheduler_publisher.assert_called_once()
    # we shall have a a new comp_runs row with the new pipeline job
    run_entry = (
        await assert_comp_runs(
            sqlalchemy_async_engine,
            expected_total=1,
            expected_state=RunningState.PUBLISHED,
            where_statement=(comp_runs.c.user_id == user["id"])
            & (comp_runs.c.project_uuid == f"{sleepers_project.uuid}"),
        )
    )[0]

    #
    # Trigger scheduling manually. since the pipeline is broken, it shall be aborted
    #
    await scheduler_api.apply(
        user_id=run_entry.user_id,
        project_id=run_entry.project_uuid,
        iteration=run_entry.iteration,
    )
    await assert_comp_runs(
        sqlalchemy_async_engine,
        expected_total=1,
        expected_state=RunningState.ABORTED,
        where_statement=(comp_runs.c.user_id == user["id"])
        & (comp_runs.c.project_uuid == f"{sleepers_project.uuid}"),
    )


async def test_task_progress_triggers(
    with_disabled_auto_scheduling: mock.Mock,
    with_disabled_scheduler_publisher: mock.Mock,
    initialized_app: FastAPI,
    mocked_dask_client: mock.MagicMock,
    scheduler_api: BaseCompScheduler,
    sqlalchemy_async_engine: AsyncEngine,
    published_project: PublishedProject,
    mocked_parse_output_data_fct: mock.Mock,
    mocked_clean_task_output_and_log_files_if_invalid: mock.Mock,
    run_metadata: RunMetadataDict,
):
    _with_mock_send_computation_tasks(published_project.tasks, mocked_dask_client)
    _run_in_db, expected_published_tasks = await _assert_start_pipeline(
        initialized_app,
        sqlalchemy_async_engine=sqlalchemy_async_engine,
        published_project=published_project,
        run_metadata=run_metadata,
    )
    # -------------------------------------------------------------------------------
    # 1. first run will move comp_tasks to PENDING so the dask-worker can take them
    expected_pending_tasks, _ = await _assert_publish_in_dask_backend(
        sqlalchemy_async_engine,
        published_project,
        expected_published_tasks,
        mocked_dask_client,
        scheduler_api,
    )

    # send some progress
    started_task = expected_pending_tasks[0]
    assert started_task.job_id
    assert published_project.project.prj_owner
    for progress in [-1, 0, 0.3, 0.5, 1, 1.5, 0.7, 0, 20]:
        progress_event = TaskProgressEvent(
            job_id=started_task.job_id,
            progress=progress,
            task_owner=TaskOwner(
                user_id=published_project.project.prj_owner,
                project_id=published_project.project.uuid,
                node_id=started_task.node_id,
                parent_node_id=None,
                parent_project_id=None,
            ),
        )
        await cast(  # noqa: SLF001
            DaskScheduler, scheduler_api
        )._task_progress_change_handler(progress_event.model_dump_json())
        # NOTE: not sure whether it should switch to STARTED.. it would make sense
        await assert_comp_tasks(
            sqlalchemy_async_engine,
            project_uuid=published_project.project.uuid,
            task_ids=[started_task.node_id],
            expected_state=RunningState.STARTED,
            expected_progress=min(max(0, progress), 1),
        )


@pytest.mark.parametrize(
    "backend_error",
    [
        ComputationalBackendNotConnectedError(msg="faked disconnected backend"),
        ComputationalSchedulerChangedError(
            original_scheduler_id="some_old_scheduler_id",
            current_scheduler_id="some_new_scheduler_id",
        ),
    ],
)
async def test_handling_of_disconnected_scheduler_dask(
    with_disabled_auto_scheduling: mock.Mock,
    with_disabled_scheduler_publisher: mock.Mock,
    initialized_app: FastAPI,
    mocked_dask_client: mock.MagicMock,
    scheduler_api: BaseCompScheduler,
    sqlalchemy_async_engine: AsyncEngine,
    mocker: MockerFixture,
    published_project: PublishedProject,
    backend_error: ComputationalSchedulerError,
    run_metadata: RunMetadataDict,
):
    # this will create a non connected backend issue that will trigger re-connection
    mocked_dask_client_send_task = mocker.patch(
        "simcore_service_director_v2.modules.comp_scheduler._scheduler_dask.DaskClient.send_computation_tasks",
        side_effect=backend_error,
    )
    assert mocked_dask_client_send_task

    # running the pipeline will now raise and the tasks are set back to PUBLISHED
    assert published_project.project.prj_owner
    await run_new_pipeline(
        initialized_app,
        user_id=published_project.project.prj_owner,
        project_id=published_project.project.uuid,
        cluster_id=DEFAULT_CLUSTER_ID,
        run_metadata=run_metadata,
        use_on_demand_clusters=False,
    )

    # since there is no cluster, there is no dask-scheduler,
    # the tasks shall all still be in PUBLISHED state now
    runs_in_db = await assert_comp_runs(
        sqlalchemy_async_engine,
        expected_total=1,
        expected_state=RunningState.PUBLISHED,
        where_statement=and_(
            comp_runs.c.user_id == published_project.project.prj_owner,
            comp_runs.c.project_uuid == f"{published_project.project.uuid}",
        ),
    )
    run_in_db = runs_in_db[0]

    await assert_comp_tasks(
        sqlalchemy_async_engine,
        project_uuid=published_project.project.uuid,
        task_ids=[t.node_id for t in published_project.tasks],
        expected_state=RunningState.PUBLISHED,
        expected_progress=None,
    )
    # on the next iteration of the pipeline it will try to re-connect
    # now try to abort the tasks since we are wondering what is happening, this should auto-trigger the scheduler
    await stop_pipeline(
        initialized_app,
        user_id=published_project.project.prj_owner,
        project_id=published_project.project.uuid,
    )
    # we ensure the scheduler was run
    await scheduler_api.apply(
        user_id=run_in_db.user_id,
        project_id=run_in_db.project_uuid,
        iteration=run_in_db.iteration,
    )
    # after this step the tasks are marked as ABORTED
    await assert_comp_tasks(
        sqlalchemy_async_engine,
        project_uuid=published_project.project.uuid,
        task_ids=[
            t.node_id
            for t in published_project.tasks
            if t.node_class == NodeClass.COMPUTATIONAL
        ],
        expected_state=RunningState.ABORTED,
        expected_progress=1,
    )
    # then we have another scheduler run
    await scheduler_api.apply(
        user_id=run_in_db.user_id,
        project_id=run_in_db.project_uuid,
        iteration=run_in_db.iteration,
    )
    # now the run should be ABORTED
    await assert_comp_runs(
        sqlalchemy_async_engine,
        expected_total=1,
        expected_state=RunningState.ABORTED,
        where_statement=and_(
            comp_runs.c.user_id == published_project.project.prj_owner,
            comp_runs.c.project_uuid == f"{published_project.project.uuid}",
        ),
    )


@dataclass(frozen=True, kw_only=True)
class RebootState:
    dask_task_status: DaskClientTaskState
    task_result: Exception | TaskOutputData
    expected_task_state_group1: RunningState
    expected_task_progress_group1: float
    expected_task_state_group2: RunningState
    expected_task_progress_group2: float
    expected_run_state: RunningState


@pytest.mark.parametrize(
    "reboot_state",
    [
        pytest.param(
            RebootState(
                dask_task_status=DaskClientTaskState.LOST,
                task_result=ComputationalBackendTaskNotFoundError(job_id="fake_job_id"),
                expected_task_state_group1=RunningState.FAILED,
                expected_task_progress_group1=1,
                expected_task_state_group2=RunningState.ABORTED,
                expected_task_progress_group2=1,
                expected_run_state=RunningState.FAILED,
            ),
            id="reboot with lost tasks",
        ),
        pytest.param(
            RebootState(
                dask_task_status=DaskClientTaskState.ABORTED,
                task_result=TaskCancelledError(job_id="fake_job_id"),
                expected_task_state_group1=RunningState.ABORTED,
                expected_task_progress_group1=1,
                expected_task_state_group2=RunningState.ABORTED,
                expected_task_progress_group2=1,
                expected_run_state=RunningState.ABORTED,
            ),
            id="reboot with aborted tasks",
        ),
        pytest.param(
            RebootState(
                dask_task_status=DaskClientTaskState.ERRED,
                task_result=ValueError("some error during the call"),
                expected_task_state_group1=RunningState.FAILED,
                expected_task_progress_group1=1,
                expected_task_state_group2=RunningState.ABORTED,
                expected_task_progress_group2=1,
                expected_run_state=RunningState.FAILED,
            ),
            id="reboot with failed tasks",
        ),
        pytest.param(
            RebootState(
                dask_task_status=DaskClientTaskState.PENDING_OR_STARTED,
                task_result=ComputationalBackendTaskResultsNotReadyError(
                    job_id="fake_job_id"
                ),
                expected_task_state_group1=RunningState.STARTED,
                expected_task_progress_group1=0,
                expected_task_state_group2=RunningState.STARTED,
                expected_task_progress_group2=0,
                expected_run_state=RunningState.STARTED,
            ),
            id="reboot with running tasks",
        ),
        pytest.param(
            RebootState(
                dask_task_status=DaskClientTaskState.SUCCESS,
                task_result=TaskOutputData.model_validate({"whatever_output": 123}),
                expected_task_state_group1=RunningState.SUCCESS,
                expected_task_progress_group1=1,
                expected_task_state_group2=RunningState.SUCCESS,
                expected_task_progress_group2=1,
                expected_run_state=RunningState.SUCCESS,
            ),
            id="reboot with completed tasks",
        ),
    ],
)
async def test_handling_scheduled_tasks_after_director_reboots(
    with_disabled_auto_scheduling: mock.Mock,
    with_disabled_scheduler_publisher: mock.Mock,
    mocked_dask_client: mock.MagicMock,
    sqlalchemy_async_engine: AsyncEngine,
    running_project: RunningProject,
    scheduler_api: BaseCompScheduler,
    mocked_parse_output_data_fct: mock.Mock,
    mocked_clean_task_output_fct: mock.Mock,
    reboot_state: RebootState,
):
    """After the dask client is rebooted, or that the director-v2 reboots the dv-2 internal scheduler
    shall continue scheduling correctly. Even though the task might have continued to run
    in the dask-scheduler."""

    async def mocked_get_tasks_status(job_ids: list[str]) -> list[DaskClientTaskState]:
        return [reboot_state.dask_task_status for j in job_ids]

    mocked_dask_client.get_tasks_status.side_effect = mocked_get_tasks_status

    async def mocked_get_task_result(_job_id: str) -> TaskOutputData:
        if isinstance(reboot_state.task_result, Exception):
            raise reboot_state.task_result
        return reboot_state.task_result

    mocked_dask_client.get_task_result.side_effect = mocked_get_task_result
    assert running_project.project.prj_owner
    await scheduler_api.apply(
        user_id=running_project.project.prj_owner,
        project_id=running_project.project.uuid,
        iteration=1,
    )
    # the status will be called once for all RUNNING tasks
    mocked_dask_client.get_tasks_status.assert_called_once()
    if reboot_state.expected_run_state in COMPLETED_STATES:
        mocked_dask_client.get_task_result.assert_has_calls(
            [
                mock.call(t.job_id)
                for t in running_project.tasks
                if t.node_class == NodeClass.COMPUTATIONAL
            ],
            any_order=True,
        )
    else:
        mocked_dask_client.get_task_result.assert_not_called()
    if reboot_state.expected_run_state in [RunningState.ABORTED, RunningState.FAILED]:
        # the clean up of the outputs should be done
        mocked_clean_task_output_fct.assert_has_calls(
            [
                mock.call(
                    mock.ANY,
                    running_project.project.prj_owner,
                    running_project.project.uuid,
                    t.node_id,
                )
                for t in running_project.tasks
                if t.node_class == NodeClass.COMPUTATIONAL
            ],
            any_order=True,
        )
    else:
        mocked_clean_task_output_fct.assert_not_called()

    await assert_comp_tasks(
        sqlalchemy_async_engine,
        project_uuid=running_project.project.uuid,
        task_ids=[
            running_project.tasks[1].node_id,
            running_project.tasks[2].node_id,
            running_project.tasks[3].node_id,
        ],
        expected_state=reboot_state.expected_task_state_group1,
        expected_progress=reboot_state.expected_task_progress_group1,
    )
    await assert_comp_tasks(
        sqlalchemy_async_engine,
        project_uuid=running_project.project.uuid,
        task_ids=[running_project.tasks[4].node_id],
        expected_state=reboot_state.expected_task_state_group2,
        expected_progress=reboot_state.expected_task_progress_group2,
    )
    assert running_project.project.prj_owner
    await assert_comp_runs(
        sqlalchemy_async_engine,
        expected_total=1,
        expected_state=reboot_state.expected_run_state,
        where_statement=and_(
            comp_runs.c.user_id == running_project.project.prj_owner,
            comp_runs.c.project_uuid == f"{running_project.project.uuid}",
        ),
    )


async def test_handling_cancellation_of_jobs_after_reboot(
    with_disabled_auto_scheduling: mock.Mock,
    with_disabled_scheduler_publisher: mock.Mock,
    mocked_dask_client: mock.MagicMock,
    sqlalchemy_async_engine: AsyncEngine,
    running_project_mark_for_cancellation: RunningProject,
    scheduler_api: BaseCompScheduler,
    mocked_parse_output_data_fct: mock.Mock,
    mocked_clean_task_output_fct: mock.Mock,
):
    """A running pipeline was cancelled by a user and the DV-2 was restarted BEFORE
    It could actually cancel the task. On reboot the DV-2 shall recover
    and actually cancel the pipeline properly"""

    # check initial status
    run_in_db = (
        await assert_comp_runs(
            sqlalchemy_async_engine,
            expected_total=1,
            expected_state=RunningState.STARTED,
            where_statement=and_(
                comp_runs.c.user_id
                == running_project_mark_for_cancellation.project.prj_owner,
                comp_runs.c.project_uuid
                == f"{running_project_mark_for_cancellation.project.uuid}",
            ),
        )
    )[0]

    await assert_comp_tasks(
        sqlalchemy_async_engine,
        project_uuid=running_project_mark_for_cancellation.project.uuid,
        task_ids=[t.node_id for t in running_project_mark_for_cancellation.tasks],
        expected_state=RunningState.STARTED,
        expected_progress=0,
    )

    # the backend shall report the tasks as running
    async def mocked_get_tasks_status(job_ids: list[str]) -> list[DaskClientTaskState]:
        return [DaskClientTaskState.PENDING_OR_STARTED for j in job_ids]

    mocked_dask_client.get_tasks_status.side_effect = mocked_get_tasks_status
    # Running the scheduler, should actually cancel the run now
    await scheduler_api.apply(
        user_id=run_in_db.user_id,
        project_id=run_in_db.project_uuid,
        iteration=run_in_db.iteration,
    )
    mocked_dask_client.abort_computation_task.assert_called()
    assert mocked_dask_client.abort_computation_task.call_count == len(
        [
            t.node_id
            for t in running_project_mark_for_cancellation.tasks
            if t.node_class == NodeClass.COMPUTATIONAL
        ]
    )
    # in the DB they are still running, they will be stopped in the next iteration
    await assert_comp_tasks(
        sqlalchemy_async_engine,
        project_uuid=running_project_mark_for_cancellation.project.uuid,
        task_ids=[
            t.node_id
            for t in running_project_mark_for_cancellation.tasks
            if t.node_class == NodeClass.COMPUTATIONAL
        ],
        expected_state=RunningState.STARTED,
        expected_progress=0,
    )
    await assert_comp_runs(
        sqlalchemy_async_engine,
        expected_total=1,
        expected_state=RunningState.STARTED,
        where_statement=and_(
            comp_runs.c.user_id
            == running_project_mark_for_cancellation.project.prj_owner,
            comp_runs.c.project_uuid
            == f"{running_project_mark_for_cancellation.project.uuid}",
        ),
    )

    # the backend shall now report the tasks as aborted
    async def mocked_get_tasks_status_aborted(
        job_ids: list[str],
    ) -> list[DaskClientTaskState]:
        return [DaskClientTaskState.ABORTED for j in job_ids]

    mocked_dask_client.get_tasks_status.side_effect = mocked_get_tasks_status_aborted

    async def _return_random_task_result(job_id) -> TaskOutputData:
        raise TaskCancelledError

    mocked_dask_client.get_task_result.side_effect = _return_random_task_result
    await scheduler_api.apply(
        user_id=run_in_db.user_id,
        project_id=run_in_db.project_uuid,
        iteration=run_in_db.iteration,
    )
    # now should be stopped
    await assert_comp_tasks(
        sqlalchemy_async_engine,
        project_uuid=running_project_mark_for_cancellation.project.uuid,
        task_ids=[
            t.node_id
            for t in running_project_mark_for_cancellation.tasks
            if t.node_class == NodeClass.COMPUTATIONAL
        ],
        expected_state=RunningState.ABORTED,
        expected_progress=1,
    )
    await assert_comp_runs(
        sqlalchemy_async_engine,
        expected_total=1,
        expected_state=RunningState.ABORTED,
        where_statement=and_(
            comp_runs.c.user_id
            == running_project_mark_for_cancellation.project.prj_owner,
            comp_runs.c.project_uuid
            == f"{running_project_mark_for_cancellation.project.uuid}",
        ),
    )
    mocked_clean_task_output_fct.assert_called()


@pytest.fixture
def with_fast_service_heartbeat_s(monkeypatch: pytest.MonkeyPatch) -> int:
    seconds = 1
    monkeypatch.setenv(
        "SERVICE_TRACKING_HEARTBEAT", f"{datetime.timedelta(seconds=seconds)}"
    )
    return seconds


async def test_running_pipeline_triggers_heartbeat(
    with_disabled_auto_scheduling: mock.Mock,
    with_disabled_scheduler_publisher: mock.Mock,
    with_fast_service_heartbeat_s: int,
    initialized_app: FastAPI,
    mocked_dask_client: mock.MagicMock,
    scheduler_api: BaseCompScheduler,
    sqlalchemy_async_engine: AsyncEngine,
    published_project: PublishedProject,
    resource_tracking_rabbit_client_parser: mock.AsyncMock,
    run_metadata: RunMetadataDict,
):
    _with_mock_send_computation_tasks(published_project.tasks, mocked_dask_client)
    run_in_db, expected_published_tasks = await _assert_start_pipeline(
        initialized_app,
        sqlalchemy_async_engine=sqlalchemy_async_engine,
        published_project=published_project,
        run_metadata=run_metadata,
    )
    # -------------------------------------------------------------------------------
    # 1. first run will move comp_tasks to PENDING so the dask-worker can take them
    expected_pending_tasks, _ = await _assert_publish_in_dask_backend(
        sqlalchemy_async_engine,
        published_project,
        expected_published_tasks,
        mocked_dask_client,
        scheduler_api,
    )
    # -------------------------------------------------------------------------------
    # 2. the "worker" starts processing a task
    exp_started_task = expected_pending_tasks[0]
    expected_pending_tasks.remove(exp_started_task)

    async def _return_1st_task_running(job_ids: list[str]) -> list[DaskClientTaskState]:
        return [
            (
                DaskClientTaskState.PENDING_OR_STARTED
                if job_id == exp_started_task.job_id
                else DaskClientTaskState.PENDING
            )
            for job_id in job_ids
        ]

    mocked_dask_client.get_tasks_status.side_effect = _return_1st_task_running
    assert exp_started_task.job_id
    assert published_project.project.prj_owner
    await _trigger_progress_event(
        scheduler_api,
        job_id=exp_started_task.job_id,
        user_id=published_project.project.prj_owner,
        project_id=exp_started_task.project_id,
        node_id=exp_started_task.node_id,
    )
    await scheduler_api.apply(
        user_id=run_in_db.user_id,
        project_id=run_in_db.project_uuid,
        iteration=run_in_db.iteration,
    )

    messages = await _assert_message_received(
        resource_tracking_rabbit_client_parser,
        1,
        RabbitResourceTrackingStartedMessage.model_validate_json,
    )
    assert messages[0].node_id == exp_started_task.node_id

    # -------------------------------------------------------------------------------
    # 3. wait a bit and run again we should get another heartbeat, but only one!
    await asyncio.sleep(with_fast_service_heartbeat_s + 1)
    await scheduler_api.apply(
        user_id=run_in_db.user_id,
        project_id=run_in_db.project_uuid,
        iteration=run_in_db.iteration,
    )
    await scheduler_api.apply(
        user_id=run_in_db.user_id,
        project_id=run_in_db.project_uuid,
        iteration=run_in_db.iteration,
    )
    messages = await _assert_message_received(
        resource_tracking_rabbit_client_parser,
        1,
        RabbitResourceTrackingHeartbeatMessage.model_validate_json,
    )
    assert isinstance(messages[0], RabbitResourceTrackingHeartbeatMessage)

    # -------------------------------------------------------------------------------
    # 4. wait a bit and run again we should get another heartbeat, but only one!
    await asyncio.sleep(with_fast_service_heartbeat_s + 1)
    await scheduler_api.apply(
        user_id=run_in_db.user_id,
        project_id=run_in_db.project_uuid,
        iteration=run_in_db.iteration,
    )
    await scheduler_api.apply(
        user_id=run_in_db.user_id,
        project_id=run_in_db.project_uuid,
        iteration=run_in_db.iteration,
    )
    messages = await _assert_message_received(
        resource_tracking_rabbit_client_parser,
        1,
        RabbitResourceTrackingHeartbeatMessage.model_validate_json,
    )
    assert isinstance(messages[0], RabbitResourceTrackingHeartbeatMessage)


@pytest.fixture
async def mocked_get_or_create_cluster(mocker: MockerFixture) -> mock.Mock:
    return mocker.patch(
        "simcore_service_director_v2.modules.comp_scheduler._scheduler_dask.get_or_create_on_demand_cluster",
        autospec=True,
    )


async def test_pipeline_with_on_demand_cluster_with_not_ready_backend_waits(
    with_disabled_auto_scheduling: mock.Mock,
    with_disabled_scheduler_publisher: mock.Mock,
    initialized_app: FastAPI,
    scheduler_api: BaseCompScheduler,
    sqlalchemy_async_engine: AsyncEngine,
    published_project: PublishedProject,
    run_metadata: RunMetadataDict,
    mocked_get_or_create_cluster: mock.Mock,
    faker: Faker,
):
    mocked_get_or_create_cluster.side_effect = (
        ComputationalBackendOnDemandNotReadyError(
            eta=faker.time_delta(datetime.timedelta(hours=1))
        )
    )
    # running the pipeline will trigger a call to the clusters-keeper
    assert published_project.project.prj_owner
    await run_new_pipeline(
        initialized_app,
        user_id=published_project.project.prj_owner,
        project_id=published_project.project.uuid,
        cluster_id=DEFAULT_CLUSTER_ID,
        run_metadata=run_metadata,
        use_on_demand_clusters=True,
    )

    # we ask to use an on-demand cluster, therefore the tasks are published first
    run_in_db = (
        await assert_comp_runs(
            sqlalchemy_async_engine,
            expected_total=1,
            expected_state=RunningState.PUBLISHED,
            where_statement=and_(
                comp_runs.c.user_id == published_project.project.prj_owner,
                comp_runs.c.project_uuid == f"{published_project.project.uuid}",
            ),
        )
    )[0]
    await assert_comp_tasks(
        sqlalchemy_async_engine,
        project_uuid=published_project.project.uuid,
        task_ids=[t.node_id for t in published_project.tasks],
        expected_state=RunningState.PUBLISHED,
        expected_progress=None,
    )
    mocked_get_or_create_cluster.assert_not_called()
    # now it should switch to waiting
    expected_waiting_tasks = [
        published_project.tasks[1],
        published_project.tasks[3],
    ]
    await scheduler_api.apply(
        user_id=run_in_db.user_id,
        project_id=run_in_db.project_uuid,
        iteration=run_in_db.iteration,
    )
    mocked_get_or_create_cluster.assert_called()
    assert mocked_get_or_create_cluster.call_count == 1
    mocked_get_or_create_cluster.reset_mock()
    await assert_comp_runs(
        sqlalchemy_async_engine,
        expected_total=1,
        expected_state=RunningState.WAITING_FOR_CLUSTER,
        where_statement=and_(
            comp_runs.c.user_id == published_project.project.prj_owner,
            comp_runs.c.project_uuid == f"{published_project.project.uuid}",
        ),
    )
    await assert_comp_tasks(
        sqlalchemy_async_engine,
        project_uuid=published_project.project.uuid,
        task_ids=[t.node_id for t in expected_waiting_tasks],
        expected_state=RunningState.WAITING_FOR_CLUSTER,
        expected_progress=None,
    )
    # again will trigger the same response
    await scheduler_api.apply(
        user_id=run_in_db.user_id,
        project_id=run_in_db.project_uuid,
        iteration=run_in_db.iteration,
    )
    mocked_get_or_create_cluster.assert_called()
    assert mocked_get_or_create_cluster.call_count == 1
    mocked_get_or_create_cluster.reset_mock()
    await assert_comp_runs(
        sqlalchemy_async_engine,
        expected_total=1,
        expected_state=RunningState.WAITING_FOR_CLUSTER,
        where_statement=and_(
            comp_runs.c.user_id == published_project.project.prj_owner,
            comp_runs.c.project_uuid == f"{published_project.project.uuid}",
        ),
    )
    await assert_comp_tasks(
        sqlalchemy_async_engine,
        project_uuid=published_project.project.uuid,
        task_ids=[t.node_id for t in expected_waiting_tasks],
        expected_state=RunningState.WAITING_FOR_CLUSTER,
        expected_progress=None,
    )


@pytest.mark.parametrize(
    "get_or_create_exception",
    [ClustersKeeperNotAvailableError],
)
async def test_pipeline_with_on_demand_cluster_with_no_clusters_keeper_fails(
    with_disabled_auto_scheduling: mock.Mock,
    with_disabled_scheduler_publisher: mock.Mock,
    initialized_app: FastAPI,
    scheduler_api: BaseCompScheduler,
    sqlalchemy_async_engine: AsyncEngine,
    published_project: PublishedProject,
    run_metadata: RunMetadataDict,
    mocked_get_or_create_cluster: mock.Mock,
    get_or_create_exception: Exception,
):
    # needs to change: https://github.com/ITISFoundation/osparc-simcore/issues/6817

    mocked_get_or_create_cluster.side_effect = get_or_create_exception
    # running the pipeline will trigger a call to the clusters-keeper
    assert published_project.project.prj_owner
    await run_new_pipeline(
        initialized_app,
        user_id=published_project.project.prj_owner,
        project_id=published_project.project.uuid,
        cluster_id=DEFAULT_CLUSTER_ID,
        run_metadata=run_metadata,
        use_on_demand_clusters=True,
    )

    # we ask to use an on-demand cluster, therefore the tasks are published first
    run_in_db = (
        await assert_comp_runs(
            sqlalchemy_async_engine,
            expected_total=1,
            expected_state=RunningState.PUBLISHED,
            where_statement=and_(
                comp_runs.c.user_id == published_project.project.prj_owner,
                comp_runs.c.project_uuid == f"{published_project.project.uuid}",
            ),
        )
    )[0]
    await assert_comp_tasks(
        sqlalchemy_async_engine,
        project_uuid=published_project.project.uuid,
        task_ids=[t.node_id for t in published_project.tasks],
        expected_state=RunningState.PUBLISHED,
        expected_progress=None,
    )
    # now it should switch to failed, the run still runs until the next iteration
    expected_failed_tasks = [
        published_project.tasks[1],
        published_project.tasks[3],
    ]
    await scheduler_api.apply(
        user_id=run_in_db.user_id,
        project_id=run_in_db.project_uuid,
        iteration=run_in_db.iteration,
    )
    mocked_get_or_create_cluster.assert_called()
    assert mocked_get_or_create_cluster.call_count == 1
    mocked_get_or_create_cluster.reset_mock()
    await assert_comp_runs(
        sqlalchemy_async_engine,
        expected_total=1,
        expected_state=RunningState.FAILED,
        where_statement=and_(
            comp_runs.c.user_id == published_project.project.prj_owner,
            comp_runs.c.project_uuid == f"{published_project.project.uuid}",
        ),
    )
    await assert_comp_tasks(
        sqlalchemy_async_engine,
        project_uuid=published_project.project.uuid,
        task_ids=[t.node_id for t in expected_failed_tasks],
        expected_state=RunningState.FAILED,
        expected_progress=1.0,
    )
    # again will not re-trigger the call to clusters-keeper
    await scheduler_api.apply(
        user_id=run_in_db.user_id,
        project_id=run_in_db.project_uuid,
        iteration=run_in_db.iteration,
    )
    mocked_get_or_create_cluster.assert_not_called()
    await assert_comp_runs(
        sqlalchemy_async_engine,
        expected_total=1,
        expected_state=RunningState.FAILED,
        where_statement=and_(
            comp_runs.c.user_id == published_project.project.prj_owner,
            comp_runs.c.project_uuid == f"{published_project.project.uuid}",
        ),
    )
    await assert_comp_tasks(
        sqlalchemy_async_engine,
        project_uuid=published_project.project.uuid,
        task_ids=[t.node_id for t in expected_failed_tasks],
        expected_state=RunningState.FAILED,
        expected_progress=1.0,
    )
