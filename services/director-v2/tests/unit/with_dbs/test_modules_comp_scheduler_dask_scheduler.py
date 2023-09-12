# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=no-value-for-parameter
# pylint:disable=protected-access
# pylint:disable=too-many-arguments
# pylint:disable=no-name-in-module
# pylint: disable=too-many-statements


import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, cast
from unittest import mock

import aiopg
import aiopg.sa
import httpx
import pytest
from _helpers import PublishedProject, RunningProject
from dask.distributed import SpecCluster
from dask_task_models_library.container_tasks.errors import TaskCancelledError
from dask_task_models_library.container_tasks.events import TaskProgressEvent
from dask_task_models_library.container_tasks.io import TaskOutputData
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
from pydantic import parse_obj_as, parse_raw_as
from pytest_mock.plugin import MockerFixture
from pytest_simcore.helpers.typing_env import EnvVarsDict
from servicelib.rabbitmq import RabbitMQClient
from settings_library.rabbit import RabbitSettings
from simcore_postgres_database.models.comp_runs import comp_runs
from simcore_postgres_database.models.comp_tasks import NodeClass, comp_tasks
from simcore_service_director_v2.core.application import init_app
from simcore_service_director_v2.core.errors import (
    ComputationalBackendNotConnectedError,
    ComputationalBackendOnDemandClustersKeeperNotReadyError,
    ComputationalBackendOnDemandNotReadyError,
    ComputationalBackendTaskNotFoundError,
    ComputationalBackendTaskResultsNotReadyError,
    ComputationalSchedulerChangedError,
    ConfigurationError,
    PipelineNotFoundError,
    SchedulerError,
)
from simcore_service_director_v2.core.settings import AppSettings
from simcore_service_director_v2.models.comp_pipelines import CompPipelineAtDB
from simcore_service_director_v2.models.comp_runs import CompRunsAtDB, RunMetadataDict
from simcore_service_director_v2.models.comp_tasks import CompTaskAtDB
from simcore_service_director_v2.modules.comp_scheduler import background_task
from simcore_service_director_v2.modules.comp_scheduler.base_scheduler import (
    BaseCompScheduler,
)
from simcore_service_director_v2.modules.comp_scheduler.dask_scheduler import (
    DaskScheduler,
)
from simcore_service_director_v2.utils.comp_scheduler import COMPLETED_STATES
from simcore_service_director_v2.utils.dask_client_utils import TaskHandlers
from starlette.testclient import TestClient
from tenacity._asyncio import AsyncRetrying
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed

pytest_simcore_core_services_selection = ["postgres", "rabbit"]
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
    )
    mocked_dask_client.register_handlers.assert_called_once_with(
        TaskHandlers(
            cast(DaskScheduler, scheduler)._task_progress_change_handler,
            cast(DaskScheduler, scheduler)._task_log_change_handler,  # noqa: SLF001
        )
    )


async def _assert_comp_run_db(
    aiopg_engine: aiopg.sa.engine.Engine,
    pub_project: PublishedProject,
    expected_state: RunningState,
) -> None:
    # check the database is correctly updated, the run is published
    async with aiopg_engine.acquire() as conn:
        result = await conn.execute(
            comp_runs.select().where(
                (comp_runs.c.user_id == pub_project.project.prj_owner)
                & (comp_runs.c.project_uuid == f"{pub_project.project.uuid}")
            )  # there is only one entry
        )
        run_entry = CompRunsAtDB.parse_obj(await result.first())
    assert (
        run_entry.result == expected_state
    ), f"comp_runs: expected state '{expected_state}, found '{run_entry.result}'"


async def _assert_comp_tasks_db(
    aiopg_engine: aiopg.sa.engine.Engine,
    project_uuid: ProjectID,
    task_ids: list[NodeID],
    *,
    expected_state: RunningState,
    expected_progress: float | None,
) -> None:
    # check the database is correctly updated, the run is published
    async with aiopg_engine.acquire() as conn:
        result = await conn.execute(
            comp_tasks.select().where(
                (comp_tasks.c.project_id == f"{project_uuid}")
                & (comp_tasks.c.node_id.in_([f"{n}" for n in task_ids]))
            )  # there is only one entry
        )
        tasks = parse_obj_as(list[CompTaskAtDB], await result.fetchall())
    assert all(
        t.state == expected_state for t in tasks
    ), f"expected state: {expected_state}, found: {[t.state for t in tasks]}"
    assert all(
        t.progress == expected_progress for t in tasks
    ), f"{expected_progress=}, found: {[t.progress for t in tasks]}"


async def run_comp_scheduler(scheduler: BaseCompScheduler) -> None:
    await scheduler.schedule_all_pipelines()


@pytest.fixture
def minimal_dask_scheduler_config(
    mock_env: EnvVarsDict,
    postgres_host_config: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
    rabbit_service: RabbitSettings,
) -> None:
    """set a minimal configuration for testing the dask connection only"""
    monkeypatch.setenv("DIRECTOR_V2_DYNAMIC_SIDECAR_ENABLED", "false")
    monkeypatch.setenv("DIRECTOR_V0_ENABLED", "0")
    monkeypatch.setenv("COMPUTATIONAL_BACKEND_DASK_CLIENT_ENABLED", "1")
    monkeypatch.setenv("COMPUTATIONAL_BACKEND_ENABLED", "1")
    monkeypatch.setenv("R_CLONE_PROVIDER", "MINIO")
    monkeypatch.setenv("S3_ENDPOINT", "endpoint")
    monkeypatch.setenv("S3_ACCESS_KEY", "access_key")
    monkeypatch.setenv("S3_SECRET_KEY", "secret_key")
    monkeypatch.setenv("S3_BUCKET_NAME", "bucket_name")
    monkeypatch.setenv("S3_SECURE", "false")


@pytest.fixture
def scheduler(
    minimal_dask_scheduler_config: None,
    aiopg_engine: aiopg.sa.engine.Engine,
    # dask_spec_local_cluster: SpecCluster,
    minimal_app: FastAPI,
) -> BaseCompScheduler:
    assert minimal_app.state.scheduler is not None
    return minimal_app.state.scheduler


@pytest.fixture
def mocked_dask_client(mocker: MockerFixture) -> mock.MagicMock:
    mocked_dask_client = mocker.patch(
        "simcore_service_director_v2.modules.dask_clients_pool.DaskClient",
        autospec=True,
    )
    mocked_dask_client.create.return_value = mocked_dask_client
    return mocked_dask_client


@pytest.fixture
def mocked_parse_output_data_fct(mocker: MockerFixture) -> mock.Mock:
    return mocker.patch(
        "simcore_service_director_v2.modules.comp_scheduler.dask_scheduler.parse_output_data",
        autospec=True,
    )


@pytest.fixture
def mocked_clean_task_output_fct(mocker: MockerFixture) -> mock.MagicMock:
    return mocker.patch(
        "simcore_service_director_v2.modules.comp_scheduler.dask_scheduler.clean_task_output_and_log_files_if_invalid",
        return_value=None,
        autospec=True,
    )


@pytest.fixture
def with_disabled_scheduler_task(mocker: MockerFixture) -> None:
    """disables the scheduler task, note that it needs to be triggered manually then"""
    mocker.patch.object(background_task, "scheduler_task")


@pytest.fixture
async def minimal_app(async_client: httpx.AsyncClient) -> FastAPI:
    # must use the minimal app from from the `async_client``
    # the`client` uses starlette's TestClient which spawns
    # a new thread on which it creates a new loop
    # causing issues downstream with coroutines not
    # being created on the same loop
    return async_client._transport.app  # type: ignore


@pytest.fixture
def mocked_clean_task_output_and_log_files_if_invalid(mocker: MockerFixture) -> None:
    mocker.patch(
        "simcore_service_director_v2.modules.comp_scheduler.dask_scheduler.clean_task_output_and_log_files_if_invalid",
        autospec=True,
    )


async def test_scheduler_gracefully_starts_and_stops(
    minimal_dask_scheduler_config: None,
    aiopg_engine: aiopg.sa.engine.Engine,
    dask_spec_local_cluster: SpecCluster,
    minimal_app: FastAPI,
):
    # check it started correctly
    assert minimal_app.state.scheduler_task is not None


@pytest.mark.parametrize(
    "missing_dependency",
    [
        "COMPUTATIONAL_BACKEND_DASK_CLIENT_ENABLED",
    ],
)
def test_scheduler_raises_exception_for_missing_dependencies(
    minimal_dask_scheduler_config: None,
    aiopg_engine: aiopg.sa.engine.Engine,
    dask_spec_local_cluster: SpecCluster,
    monkeypatch: pytest.MonkeyPatch,
    missing_dependency: str,
):
    # disable the dependency
    monkeypatch.setenv(missing_dependency, "0")
    # create the client
    settings = AppSettings.create_from_envs()
    app = init_app(settings)

    with pytest.raises(ConfigurationError):
        with TestClient(app, raise_server_exceptions=True) as _:
            pass


async def test_empty_pipeline_is_not_scheduled(
    with_disabled_scheduler_task: None,
    scheduler: BaseCompScheduler,
    registered_user: Callable[..., dict[str, Any]],
    project: Callable[..., Awaitable[ProjectAtDB]],
    pipeline: Callable[..., CompPipelineAtDB],
    aiopg_engine: aiopg.sa.engine.Engine,
    run_metadata: RunMetadataDict,
):
    user = registered_user()
    empty_project = await project(user)

    # the project is not in the comp_pipeline, therefore scheduling it should fail
    with pytest.raises(PipelineNotFoundError):
        await scheduler.run_new_pipeline(
            user_id=user["id"],
            project_id=empty_project.uuid,
            cluster_id=DEFAULT_CLUSTER_ID,
            run_metadata=run_metadata,
            use_on_demand_clusters=False,
        )
    # create the empty pipeline now
    pipeline(project_id=f"{empty_project.uuid}")

    # creating a run with an empty pipeline is useless, check the scheduler is not kicking in
    await scheduler.run_new_pipeline(
        user_id=user["id"],
        project_id=empty_project.uuid,
        cluster_id=DEFAULT_CLUSTER_ID,
        run_metadata=run_metadata,
        use_on_demand_clusters=False,
    )
    assert len(scheduler.scheduled_pipelines) == 0
    assert (
        scheduler.wake_up_event.is_set() is False
    ), "the scheduler was woken up on an empty pipeline!"
    # check the database is empty
    async with aiopg_engine.acquire() as conn:
        result = await conn.scalar(
            comp_runs.select().where(
                (comp_runs.c.user_id == user["id"])
                & (comp_runs.c.project_uuid == f"{empty_project.uuid}")
            )  # there is only one entry
        )
        assert result is None


async def test_misconfigured_pipeline_is_not_scheduled(
    with_disabled_scheduler_task: None,
    scheduler: BaseCompScheduler,
    registered_user: Callable[..., dict[str, Any]],
    project: Callable[..., Awaitable[ProjectAtDB]],
    pipeline: Callable[..., CompPipelineAtDB],
    fake_workbench_without_outputs: dict[str, Any],
    fake_workbench_adjacency: dict[str, Any],
    aiopg_engine: aiopg.sa.engine.Engine,
    run_metadata: RunMetadataDict,
):
    """A pipeline which comp_tasks are missing should not be scheduled.
    It shall be aborted and shown as such in the comp_runs db"""
    user = registered_user()
    sleepers_project = await project(user, workbench=fake_workbench_without_outputs)
    pipeline(
        project_id=f"{sleepers_project.uuid}",
        dag_adjacency_list=fake_workbench_adjacency,
    )
    # check the pipeline is correctly added to the scheduled pipelines
    await scheduler.run_new_pipeline(
        user_id=user["id"],
        project_id=sleepers_project.uuid,
        cluster_id=DEFAULT_CLUSTER_ID,
        run_metadata=run_metadata,
        use_on_demand_clusters=False,
    )
    assert len(scheduler.scheduled_pipelines) == 1
    assert (
        scheduler.wake_up_event.is_set() is True
    ), "the scheduler was NOT woken up on the scheduled pipeline!"
    for (u_id, p_id, it), params in scheduler.scheduled_pipelines.items():
        assert u_id == user["id"]
        assert p_id == sleepers_project.uuid
        assert it > 0
        assert params.mark_for_cancellation is False
    # check the database was properly updated
    async with aiopg_engine.acquire() as conn:
        result = await conn.execute(
            comp_runs.select().where(
                (comp_runs.c.user_id == user["id"])
                & (comp_runs.c.project_uuid == f"{sleepers_project.uuid}")
            )  # there is only one entry
        )
        run_entry = CompRunsAtDB.parse_obj(await result.first())
    assert run_entry.result == RunningState.PUBLISHED
    # let the scheduler kick in
    await run_comp_scheduler(scheduler)
    # check the scheduled pipelines is again empty since it's misconfigured
    assert len(scheduler.scheduled_pipelines) == 0
    # check the database entry is correctly updated
    async with aiopg_engine.acquire() as conn:
        result = await conn.execute(
            comp_runs.select().where(
                (comp_runs.c.user_id == user["id"])
                & (comp_runs.c.project_uuid == f"{sleepers_project.uuid}")
            )  # there is only one entry
        )
        run_entry = CompRunsAtDB.parse_obj(await result.first())
    assert run_entry.result == RunningState.ABORTED


async def _assert_start_pipeline(
    aiopg_engine, published_project: PublishedProject, scheduler: BaseCompScheduler
) -> list[CompTaskAtDB]:
    exp_published_tasks = deepcopy(published_project.tasks)
    assert published_project.project.prj_owner
    run_metadata = RunMetadataDict(
        node_id_names_map={},
        project_name="",
        product_name="",
        simcore_user_agent="",
        user_email="",
        wallet_id=231,
        wallet_name="",
    )
    await scheduler.run_new_pipeline(
        user_id=published_project.project.prj_owner,
        project_id=published_project.project.uuid,
        cluster_id=DEFAULT_CLUSTER_ID,
        run_metadata=run_metadata,
        use_on_demand_clusters=False,
    )
    assert len(scheduler.scheduled_pipelines) == 1, "the pipeline is not scheduled!"
    assert (
        scheduler.wake_up_event.is_set() is True
    ), "the scheduler was NOT woken up on the scheduled pipeline!"
    for (u_id, p_id, it), params in scheduler.scheduled_pipelines.items():
        assert u_id == published_project.project.prj_owner
        assert p_id == published_project.project.uuid
        assert it > 0
        assert params.mark_for_cancellation is False
        assert params.run_metadata == run_metadata

    # check the database is correctly updated, the run is published
    await _assert_comp_run_db(aiopg_engine, published_project, RunningState.PUBLISHED)
    await _assert_comp_tasks_db(
        aiopg_engine,
        published_project.project.uuid,
        [p.node_id for p in exp_published_tasks],
        expected_state=RunningState.PUBLISHED,
        expected_progress=None,
    )
    return exp_published_tasks


async def _assert_schedule_pipeline_PENDING(
    aiopg_engine,
    published_project: PublishedProject,
    published_tasks: list[CompTaskAtDB],
    mocked_dask_client: mock.MagicMock,
    scheduler: BaseCompScheduler,
) -> list[CompTaskAtDB]:
    expected_pending_tasks = [
        published_tasks[1],
        published_tasks[3],
    ]
    for p in expected_pending_tasks:
        published_tasks.remove(p)

    async def _return_tasks_pending(job_ids: list[str]) -> list[RunningState]:
        return [RunningState.PENDING for job_id in job_ids]

    mocked_dask_client.get_tasks_status.side_effect = _return_tasks_pending
    await run_comp_scheduler(scheduler)
    _assert_dask_client_correctly_initialized(mocked_dask_client, scheduler)
    await _assert_comp_run_db(aiopg_engine, published_project, RunningState.PUBLISHED)
    await _assert_comp_tasks_db(
        aiopg_engine,
        published_project.project.uuid,
        [p.node_id for p in expected_pending_tasks],
        expected_state=RunningState.PENDING,
        expected_progress=0,
    )
    # the other tasks are still waiting in published state
    await _assert_comp_tasks_db(
        aiopg_engine,
        published_project.project.uuid,
        [p.node_id for p in published_tasks],
        expected_state=RunningState.PUBLISHED,
        expected_progress=None,  # since we bypass the API entrypoint this is correct
    )
    # tasks were send to the backend
    mocked_dask_client.send_computation_tasks.assert_has_calls(
        calls=[
            mock.call(
                user_id=published_project.project.prj_owner,
                project_id=published_project.project.uuid,
                cluster_id=DEFAULT_CLUSTER_ID,
                tasks={f"{p.node_id}": p.image},
                callback=scheduler._wake_up_scheduler_now,  # noqa: SLF001
                metadata=mock.ANY,
            )
            for p in expected_pending_tasks
        ],
        any_order=True,
    )
    mocked_dask_client.send_computation_tasks.reset_mock()
    mocked_dask_client.get_tasks_status.assert_not_called()
    mocked_dask_client.get_task_result.assert_not_called()
    # there is a second run of the scheduler to move comp_runs to pending, the rest does not change
    await run_comp_scheduler(scheduler)
    await _assert_comp_run_db(aiopg_engine, published_project, RunningState.PENDING)
    await _assert_comp_tasks_db(
        aiopg_engine,
        published_project.project.uuid,
        [p.node_id for p in expected_pending_tasks],
        expected_state=RunningState.PENDING,
        expected_progress=0,
    )
    await _assert_comp_tasks_db(
        aiopg_engine,
        published_project.project.uuid,
        [p.node_id for p in published_tasks],
        expected_state=RunningState.PUBLISHED,
        expected_progress=None,  # since we bypass the API entrypoint this is correct
    )
    mocked_dask_client.send_computation_tasks.assert_not_called()
    mocked_dask_client.get_tasks_status.assert_has_calls(
        calls=[mock.call([p.job_id for p in expected_pending_tasks])], any_order=True
    )
    mocked_dask_client.get_tasks_status.reset_mock()
    mocked_dask_client.get_task_result.assert_not_called()
    return expected_pending_tasks


@pytest.fixture
async def instrumentation_rabbit_client_parser(
    rabbitmq_client: Callable[[str], RabbitMQClient], mocker: MockerFixture
) -> AsyncIterator[mock.AsyncMock]:
    client = rabbitmq_client("instrumentation_pytest_consumer")
    mock = mocker.AsyncMock(return_value=True)
    queue_name = await client.subscribe(
        InstrumentationRabbitMessage.get_channel_name(), mock
    )
    yield mock
    await client.unsubscribe(queue_name)


@pytest.fixture
async def resource_tracking_rabbit_client_parser(
    rabbitmq_client: Callable[[str], RabbitMQClient], mocker: MockerFixture
) -> AsyncIterator[mock.AsyncMock]:
    client = rabbitmq_client("resource_tracking_pytest_consumer")
    mock = mocker.AsyncMock(return_value=True)
    queue_name = await client.subscribe(
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


@pytest.mark.acceptance_test()
async def test_proper_pipeline_is_scheduled(  # noqa: PLR0915
    with_disabled_scheduler_task: None,
    mocked_dask_client: mock.MagicMock,
    scheduler: BaseCompScheduler,
    aiopg_engine: aiopg.sa.engine.Engine,
    published_project: PublishedProject,
    mocked_parse_output_data_fct: mock.Mock,
    mocked_clean_task_output_and_log_files_if_invalid: None,
    instrumentation_rabbit_client_parser: mock.AsyncMock,
    resource_tracking_rabbit_client_parser: mock.AsyncMock,
):
    expected_published_tasks = await _assert_start_pipeline(
        aiopg_engine, published_project, scheduler
    )
    # -------------------------------------------------------------------------------
    # 1. first run will move comp_tasks to PENDING so the worker can take them
    expected_pending_tasks = await _assert_schedule_pipeline_PENDING(
        aiopg_engine,
        published_project,
        expected_published_tasks,
        mocked_dask_client,
        scheduler,
    )

    # -------------------------------------------------------------------------------
    # 3. the "worker" starts processing a task
    exp_started_task = expected_pending_tasks[0]
    expected_pending_tasks.remove(exp_started_task)

    async def _return_1st_task_running(job_ids: list[str]) -> list[RunningState]:
        return [
            RunningState.STARTED
            if job_id == exp_started_task.job_id
            else RunningState.PENDING
            for job_id in job_ids
        ]

    mocked_dask_client.get_tasks_status.side_effect = _return_1st_task_running
    await run_comp_scheduler(scheduler)
    # comp_run, the comp_task switch to STARTED
    await _assert_comp_run_db(aiopg_engine, published_project, RunningState.STARTED)
    await _assert_comp_tasks_db(
        aiopg_engine,
        published_project.project.uuid,
        [exp_started_task.node_id],
        expected_state=RunningState.STARTED,
        expected_progress=0,
    )
    await _assert_comp_tasks_db(
        aiopg_engine,
        published_project.project.uuid,
        [p.node_id for p in expected_pending_tasks],
        expected_state=RunningState.PENDING,
        expected_progress=0,
    )
    await _assert_comp_tasks_db(
        aiopg_engine,
        published_project.project.uuid,
        [p.node_id for p in expected_published_tasks],
        expected_state=RunningState.PUBLISHED,
        expected_progress=None,  # since we bypass the API entrypoint this is correct
    )
    mocked_dask_client.send_computation_tasks.assert_not_called()
    mocked_dask_client.get_tasks_status.assert_called_once_with(
        [p.job_id for p in (exp_started_task, *expected_pending_tasks)],
    )
    mocked_dask_client.get_tasks_status.reset_mock()
    mocked_dask_client.get_task_result.assert_not_called()
    messages = await _assert_message_received(
        instrumentation_rabbit_client_parser, 1, InstrumentationRabbitMessage.parse_raw
    )
    assert messages[0].metrics == "service_started"
    assert messages[0].service_uuid == exp_started_task.node_id

    def _parser(x) -> RabbitResourceTrackingMessages:
        return parse_raw_as(RabbitResourceTrackingMessages, x)

    messages = await _assert_message_received(
        resource_tracking_rabbit_client_parser,
        1,
        RabbitResourceTrackingStartedMessage.parse_raw,
    )
    assert messages[0].node_id == exp_started_task.node_id

    # -------------------------------------------------------------------------------
    # 4. the "worker" completed the task successfully
    async def _return_1st_task_success(job_ids: list[str]) -> list[RunningState]:
        return [
            RunningState.SUCCESS
            if job_id == exp_started_task.job_id
            else RunningState.PENDING
            for job_id in job_ids
        ]

    mocked_dask_client.get_tasks_status.side_effect = _return_1st_task_success

    async def _return_random_task_result(job_id) -> TaskOutputData:
        return TaskOutputData.parse_obj({"out_1": None, "out_2": 45})

    mocked_dask_client.get_task_result.side_effect = _return_random_task_result
    await run_comp_scheduler(scheduler)
    await _assert_comp_run_db(aiopg_engine, published_project, RunningState.STARTED)
    await _assert_comp_tasks_db(
        aiopg_engine,
        published_project.project.uuid,
        [exp_started_task.node_id],
        expected_state=RunningState.SUCCESS,
        expected_progress=1,
    )
    messages = await _assert_message_received(
        instrumentation_rabbit_client_parser, 1, InstrumentationRabbitMessage.parse_raw
    )
    assert messages[0].metrics == "service_stopped"
    assert messages[0].service_uuid == exp_started_task.node_id
    messages = await _assert_message_received(
        resource_tracking_rabbit_client_parser,
        1,
        RabbitResourceTrackingStoppedMessage.parse_raw,
    )

    completed_tasks = [exp_started_task]
    next_pending_task = published_project.tasks[2]
    expected_pending_tasks.append(next_pending_task)
    await _assert_comp_tasks_db(
        aiopg_engine,
        published_project.project.uuid,
        [p.node_id for p in expected_pending_tasks],
        expected_state=RunningState.PENDING,
        expected_progress=0,
    )
    await _assert_comp_tasks_db(
        aiopg_engine,
        published_project.project.uuid,
        [
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
        callback=scheduler._wake_up_scheduler_now,  # noqa: SLF001
        metadata=mock.ANY,
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
    # 6. the "worker" starts processing a task
    exp_started_task = next_pending_task

    async def _return_2nd_task_running(job_ids: list[str]) -> list[RunningState]:
        return [
            RunningState.STARTED
            if job_id == exp_started_task.job_id
            else RunningState.PENDING
            for job_id in job_ids
        ]

    mocked_dask_client.get_tasks_status.side_effect = _return_2nd_task_running
    # trigger the scheduler, run state should keep to STARTED, task should be as well
    await run_comp_scheduler(scheduler)
    await _assert_comp_run_db(aiopg_engine, published_project, RunningState.STARTED)
    await _assert_comp_tasks_db(
        aiopg_engine,
        published_project.project.uuid,
        [exp_started_task.node_id],
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
        instrumentation_rabbit_client_parser, 1, InstrumentationRabbitMessage.parse_raw
    )
    assert messages[0].metrics == "service_started"
    assert messages[0].service_uuid == exp_started_task.node_id
    messages = await _assert_message_received(
        resource_tracking_rabbit_client_parser,
        1,
        RabbitResourceTrackingStartedMessage.parse_raw,
    )
    assert messages[0].node_id == exp_started_task.node_id

    # -------------------------------------------------------------------------------
    # 7. the task fails
    async def _return_2nd_task_failed(job_ids: list[str]) -> list[RunningState]:
        return [
            RunningState.FAILED
            if job_id == exp_started_task.job_id
            else RunningState.PENDING
            for job_id in job_ids
        ]

    mocked_dask_client.get_tasks_status.side_effect = _return_2nd_task_failed
    mocked_dask_client.get_task_result.side_effect = None
    await run_comp_scheduler(scheduler)
    await _assert_comp_run_db(aiopg_engine, published_project, RunningState.STARTED)
    await _assert_comp_tasks_db(
        aiopg_engine,
        published_project.project.uuid,
        [exp_started_task.node_id],
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
        instrumentation_rabbit_client_parser, 1, InstrumentationRabbitMessage.parse_raw
    )
    assert messages[0].metrics == "service_stopped"
    assert messages[0].service_uuid == exp_started_task.node_id
    messages = await _assert_message_received(
        resource_tracking_rabbit_client_parser,
        1,
        RabbitResourceTrackingStoppedMessage.parse_raw,
    )

    # -------------------------------------------------------------------------------
    # 8. the last task shall succeed
    exp_started_task = expected_pending_tasks[0]

    async def _return_3rd_task_success(job_ids: list[str]) -> list[RunningState]:
        return [
            RunningState.SUCCESS
            if job_id == exp_started_task.job_id
            else RunningState.PENDING
            for job_id in job_ids
        ]

    mocked_dask_client.get_tasks_status.side_effect = _return_3rd_task_success
    mocked_dask_client.get_task_result.side_effect = _return_random_task_result

    # trigger the scheduler, it should switch to FAILED, as we are done
    await run_comp_scheduler(scheduler)
    await _assert_comp_run_db(aiopg_engine, published_project, RunningState.FAILED)

    await _assert_comp_tasks_db(
        aiopg_engine,
        published_project.project.uuid,
        [exp_started_task.node_id],
        expected_state=RunningState.SUCCESS,
        expected_progress=1,
    )
    mocked_dask_client.send_computation_tasks.assert_not_called()
    mocked_dask_client.get_tasks_status.assert_called_once_with(
        [p.job_id for p in expected_pending_tasks]
    )
    mocked_dask_client.get_task_result.assert_called_once_with(exp_started_task.job_id)
    messages = await _assert_message_received(
        instrumentation_rabbit_client_parser, 2, InstrumentationRabbitMessage.parse_raw
    )
    # NOTE: the service was fast and went directly to success
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

    # the scheduled pipeline shall be removed
    assert scheduler.scheduled_pipelines == {}


async def test_task_progress_triggers(
    with_disabled_scheduler_task: None,
    mocked_dask_client: mock.MagicMock,
    scheduler: BaseCompScheduler,
    aiopg_engine: aiopg.sa.engine.Engine,
    published_project: PublishedProject,
    mocked_parse_output_data_fct: None,
    mocked_clean_task_output_and_log_files_if_invalid: None,
):
    expected_published_tasks = await _assert_start_pipeline(
        aiopg_engine, published_project, scheduler
    )
    # -------------------------------------------------------------------------------
    # 1. first run will move comp_tasks to PENDING so the worker can take them
    expected_pending_tasks = await _assert_schedule_pipeline_PENDING(
        aiopg_engine,
        published_project,
        expected_published_tasks,
        mocked_dask_client,
        scheduler,
    )

    # send some progress
    started_task = expected_pending_tasks[0]
    assert started_task.job_id
    for progress in [-1, 0, 0.3, 0.5, 1, 1.5, 0.7, 0, 20]:
        progress_event = TaskProgressEvent(
            job_id=started_task.job_id, progress=progress
        )
        await cast(DaskScheduler, scheduler)._task_progress_change_handler(
            progress_event.json()
        )
        # NOTE: not sure whether it should switch to STARTED.. it would make sense
        await _assert_comp_tasks_db(
            aiopg_engine,
            published_project.project.uuid,
            [started_task.node_id],
            expected_state=RunningState.PENDING,
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
async def test_handling_of_disconnected_dask_scheduler(
    with_disabled_scheduler_task: None,
    dask_spec_local_cluster: SpecCluster,
    scheduler: BaseCompScheduler,
    aiopg_engine: aiopg.sa.engine.Engine,
    mocker: MockerFixture,
    published_project: PublishedProject,
    backend_error: SchedulerError,
    run_metadata: RunMetadataDict,
):
    # this will create a non connected backend issue that will trigger re-connection
    mocked_dask_client_send_task = mocker.patch(
        "simcore_service_director_v2.modules.comp_scheduler.dask_scheduler.DaskClient.send_computation_tasks",
        side_effect=backend_error,
    )
    assert mocked_dask_client_send_task

    # running the pipeline will now raise and the tasks are set back to PUBLISHED
    assert published_project.project.prj_owner
    await scheduler.run_new_pipeline(
        user_id=published_project.project.prj_owner,
        project_id=published_project.project.uuid,
        cluster_id=DEFAULT_CLUSTER_ID,
        run_metadata=run_metadata,
        use_on_demand_clusters=False,
    )

    # since there is no cluster, there is no dask-scheduler,
    # the tasks shall all still be in PUBLISHED state now
    await _assert_comp_run_db(aiopg_engine, published_project, RunningState.PUBLISHED)

    await _assert_comp_tasks_db(
        aiopg_engine,
        published_project.project.uuid,
        [t.node_id for t in published_project.tasks],
        expected_state=RunningState.PUBLISHED,
        expected_progress=None,
    )
    # on the next iteration of the pipeline it will try to re-connect
    # now try to abort the tasks since we are wondering what is happening, this should auto-trigger the scheduler
    await scheduler.stop_pipeline(
        user_id=published_project.project.prj_owner,
        project_id=published_project.project.uuid,
    )
    # we ensure the scheduler was run
    await run_comp_scheduler(scheduler)
    # after this step the tasks are marked as ABORTED
    await _assert_comp_tasks_db(
        aiopg_engine,
        published_project.project.uuid,
        [
            t.node_id
            for t in published_project.tasks
            if t.node_class == NodeClass.COMPUTATIONAL
        ],
        expected_state=RunningState.ABORTED,
        expected_progress=1,
    )
    # then we have another scheduler run
    await run_comp_scheduler(scheduler)
    # now the run should be ABORTED
    await _assert_comp_run_db(aiopg_engine, published_project, RunningState.ABORTED)


@dataclass(frozen=True, kw_only=True)
class RebootState:
    task_status: RunningState
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
                task_status=RunningState.UNKNOWN,
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
                task_status=RunningState.ABORTED,
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
                task_status=RunningState.FAILED,
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
                task_status=RunningState.STARTED,
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
                task_status=RunningState.SUCCESS,
                task_result=TaskOutputData.parse_obj({"whatever_output": 123}),
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
async def test_handling_scheduling_after_reboot(
    with_disabled_scheduler_task: None,
    mocked_dask_client: mock.MagicMock,
    aiopg_engine: aiopg.sa.engine.Engine,
    running_project: RunningProject,
    scheduler: BaseCompScheduler,
    mocked_parse_output_data_fct: mock.MagicMock,
    mocked_clean_task_output_fct: mock.MagicMock,
    reboot_state: RebootState,
):
    """After the dask client is rebooted, or that the director-v2 reboots the scheduler
    shall continue scheduling correctly. Even though the task might have continued to run
    in the dask-scheduler."""

    async def mocked_get_tasks_status(job_ids: list[str]) -> list[RunningState]:
        return [reboot_state.task_status for j in job_ids]

    mocked_dask_client.get_tasks_status.side_effect = mocked_get_tasks_status

    async def mocked_get_task_result(_job_id: str) -> TaskOutputData:
        if isinstance(reboot_state.task_result, Exception):
            raise reboot_state.task_result
        return reboot_state.task_result

    mocked_dask_client.get_task_result.side_effect = mocked_get_task_result

    await run_comp_scheduler(scheduler)
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

    await _assert_comp_tasks_db(
        aiopg_engine,
        running_project.project.uuid,
        [
            running_project.tasks[1].node_id,
            running_project.tasks[2].node_id,
            running_project.tasks[3].node_id,
        ],
        expected_state=reboot_state.expected_task_state_group1,
        expected_progress=reboot_state.expected_task_progress_group1,
    )
    await _assert_comp_tasks_db(
        aiopg_engine,
        running_project.project.uuid,
        [running_project.tasks[4].node_id],
        expected_state=reboot_state.expected_task_state_group2,
        expected_progress=reboot_state.expected_task_progress_group2,
    )
    assert running_project.project.prj_owner
    await _assert_comp_run_db(
        aiopg_engine, running_project, reboot_state.expected_run_state
    )


@pytest.fixture
def with_fast_service_heartbeat_s(monkeypatch: pytest.MonkeyPatch) -> int:
    seconds = 1
    monkeypatch.setenv("SERVICE_TRACKING_HEARTBEAT", f"{seconds}")
    return seconds


async def test_running_pipeline_triggers_heartbeat(
    with_disabled_scheduler_task: None,
    with_fast_service_heartbeat_s: int,
    mocked_dask_client: mock.MagicMock,
    scheduler: BaseCompScheduler,
    aiopg_engine: aiopg.sa.engine.Engine,
    published_project: PublishedProject,
    resource_tracking_rabbit_client_parser: mock.AsyncMock,
):
    expected_published_tasks = await _assert_start_pipeline(
        aiopg_engine, published_project, scheduler
    )
    # -------------------------------------------------------------------------------
    # 1. first run will move comp_tasks to PENDING so the worker can take them
    expected_pending_tasks = await _assert_schedule_pipeline_PENDING(
        aiopg_engine,
        published_project,
        expected_published_tasks,
        mocked_dask_client,
        scheduler,
    )
    # -------------------------------------------------------------------------------
    # 2. the "worker" starts processing a task
    exp_started_task = expected_pending_tasks[0]
    expected_pending_tasks.remove(exp_started_task)

    async def _return_1st_task_running(job_ids: list[str]) -> list[RunningState]:
        return [
            RunningState.STARTED
            if job_id == exp_started_task.job_id
            else RunningState.PENDING
            for job_id in job_ids
        ]

    mocked_dask_client.get_tasks_status.side_effect = _return_1st_task_running
    await run_comp_scheduler(scheduler)

    messages = await _assert_message_received(
        resource_tracking_rabbit_client_parser,
        1,
        RabbitResourceTrackingStartedMessage.parse_raw,
    )
    assert messages[0].node_id == exp_started_task.node_id

    # -------------------------------------------------------------------------------
    # 3. wait a bit and run again we should get another heartbeat, but only one!
    await asyncio.sleep(with_fast_service_heartbeat_s + 1)
    await run_comp_scheduler(scheduler)
    await run_comp_scheduler(scheduler)
    messages = await _assert_message_received(
        resource_tracking_rabbit_client_parser,
        1,
        RabbitResourceTrackingHeartbeatMessage.parse_raw,
    )
    assert isinstance(messages[0], RabbitResourceTrackingHeartbeatMessage)

    # -------------------------------------------------------------------------------
    # 4. wait a bit and run again we should get another heartbeat, but only one!
    await asyncio.sleep(with_fast_service_heartbeat_s + 1)
    await run_comp_scheduler(scheduler)
    await run_comp_scheduler(scheduler)
    messages = await _assert_message_received(
        resource_tracking_rabbit_client_parser,
        1,
        RabbitResourceTrackingHeartbeatMessage.parse_raw,
    )
    assert isinstance(messages[0], RabbitResourceTrackingHeartbeatMessage)


@pytest.fixture
async def mocked_get_or_create_cluster(mocker: MockerFixture) -> mock.Mock:
    return mocker.patch(
        "simcore_service_director_v2.modules.comp_scheduler.dask_scheduler.get_or_create_on_demand_cluster",
        autospec=True,
    )


async def test_pipeline_with_on_demand_cluster_with_not_ready_backend_waits(
    with_disabled_scheduler_task: None,
    scheduler: BaseCompScheduler,
    aiopg_engine: aiopg.sa.engine.Engine,
    published_project: PublishedProject,
    run_metadata: RunMetadataDict,
    mocked_get_or_create_cluster: mock.Mock,
):
    mocked_get_or_create_cluster.side_effect = ComputationalBackendOnDemandNotReadyError
    # running the pipeline will trigger a call to the clusters-keeper
    assert published_project.project.prj_owner
    await scheduler.run_new_pipeline(
        user_id=published_project.project.prj_owner,
        project_id=published_project.project.uuid,
        cluster_id=DEFAULT_CLUSTER_ID,
        run_metadata=run_metadata,
        use_on_demand_clusters=True,
    )

    # we ask to use an on-demand cluster, therefore the tasks are published first
    await _assert_comp_run_db(
        aiopg_engine, published_project, RunningState.WAITING_FOR_CLUSTER
    )
    await _assert_comp_tasks_db(
        aiopg_engine,
        published_project.project.uuid,
        [t.node_id for t in published_project.tasks],
        expected_state=RunningState.WAITING_FOR_CLUSTER,
        expected_progress=None,
    )


async def test_pipeline_with_on_demand_cluster_with_no_clusters_keeper_fails(
    with_disabled_scheduler_task: None,
    scheduler: BaseCompScheduler,
    aiopg_engine: aiopg.sa.engine.Engine,
    published_project: PublishedProject,
    run_metadata: RunMetadataDict,
    mocked_get_or_create_cluster: mock.Mock,
):
    mocked_get_or_create_cluster.side_effect = (
        ComputationalBackendOnDemandClustersKeeperNotReadyError
    )
    # running the pipeline will trigger a call to the clusters-keeper
    assert published_project.project.prj_owner
    await scheduler.run_new_pipeline(
        user_id=published_project.project.prj_owner,
        project_id=published_project.project.uuid,
        cluster_id=DEFAULT_CLUSTER_ID,
        run_metadata=run_metadata,
        use_on_demand_clusters=True,
    )

    # we ask to use an on-demand cluster, therefore the tasks are published first
    await _assert_comp_run_db(aiopg_engine, published_project, RunningState.FAILED)
    await _assert_comp_tasks_db(
        aiopg_engine,
        published_project.project.uuid,
        [t.node_id for t in published_project.tasks],
        expected_state=RunningState.FAILED,
        expected_progress=None,
    )


async def test_pipeline_with_on_demand_cluster_that_raises_anythin_fails_pipeline(
    with_disabled_scheduler_task: None,
    scheduler: BaseCompScheduler,
    aiopg_engine: aiopg.sa.engine.Engine,
    published_project: PublishedProject,
    run_metadata: RunMetadataDict,
    mocked_get_or_create_cluster: mock.Mock,
):
    mocked_get_or_create_cluster.side_effect = RuntimeError("faked error")
    # running the pipeline will trigger a call to the clusters-keeper
    assert published_project.project.prj_owner
    await scheduler.run_new_pipeline(
        user_id=published_project.project.prj_owner,
        project_id=published_project.project.uuid,
        cluster_id=DEFAULT_CLUSTER_ID,
        run_metadata=run_metadata,
        use_on_demand_clusters=True,
    )

    # we ask to use an on-demand cluster, therefore the tasks are published first
    await _assert_comp_run_db(aiopg_engine, published_project, RunningState.FAILED)
    await _assert_comp_tasks_db(
        aiopg_engine,
        published_project.project.uuid,
        [t.node_id for t in published_project.tasks],
        expected_state=RunningState.FAILED,
        expected_progress=None,
    )
