# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=no-value-for-parameter
# pylint:disable=protected-access
# pylint:disable=too-many-arguments


import asyncio
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterator, List, cast
from unittest import mock

import aiopg
import pytest
from _pytest.monkeypatch import MonkeyPatch
from dask.distributed import LocalCluster, SpecCluster
from fastapi.applications import FastAPI
from models_library.projects import ProjectAtDB, ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.projects_state import RunningState
from pydantic import PositiveInt
from pydantic.tools import parse_obj_as
from pytest_mock.plugin import MockerFixture
from simcore_postgres_database.models.comp_pipeline import StateType
from simcore_postgres_database.models.comp_runs import comp_runs
from simcore_postgres_database.models.comp_tasks import comp_tasks
from simcore_service_director_v2.core.application import init_app
from simcore_service_director_v2.core.errors import (
    ComputationalBackendNotConnectedError,
    ConfigurationError,
    PipelineNotFoundError,
)
from simcore_service_director_v2.core.settings import AppSettings
from simcore_service_director_v2.models.domains.comp_pipelines import CompPipelineAtDB
from simcore_service_director_v2.models.domains.comp_runs import CompRunsAtDB
from simcore_service_director_v2.models.domains.comp_tasks import CompTaskAtDB
from simcore_service_director_v2.models.schemas.constants import UserID
from simcore_service_director_v2.modules.comp_scheduler.base_scheduler import (
    BaseCompScheduler,
)
from simcore_service_director_v2.modules.comp_scheduler.dask_scheduler import (
    DaskScheduler,
)
from starlette.testclient import TestClient

pytest_simcore_core_services_selection = ["postgres"]
pytest_simcore_ops_services_selection = ["adminer"]


@pytest.fixture()
def mocked_rabbit_mq_client(mocker: MockerFixture):
    mocker.patch(
        "simcore_service_director_v2.core.application.rabbitmq.RabbitMQClient",
        autospec=True,
    )


@pytest.fixture
def minimal_dask_scheduler_config(
    mock_env: None,
    postgres_host_config: Dict[str, str],
    monkeypatch: MonkeyPatch,
    mocked_rabbit_mq_client: None,
) -> None:
    """set a minimal configuration for testing the dask connection only"""
    monkeypatch.setenv("DIRECTOR_V2_DYNAMIC_SIDECAR_ENABLED", "false")
    monkeypatch.setenv("DIRECTOR_V0_ENABLED", "0")
    monkeypatch.setenv("DIRECTOR_V2_POSTGRES_ENABLED", "1")
    monkeypatch.setenv("DIRECTOR_V2_CELERY_ENABLED", "0")
    monkeypatch.setenv("DIRECTOR_V2_CELERY_SCHEDULER_ENABLED", "0")
    monkeypatch.setenv("DIRECTOR_V2_DASK_CLIENT_ENABLED", "1")
    monkeypatch.setenv("DIRECTOR_V2_DASK_SCHEDULER_ENABLED", "1")


async def test_scheduler_gracefully_starts_and_stops(
    minimal_dask_scheduler_config: None,
    aiopg_engine: Iterator[aiopg.sa.engine.Engine],  # type: ignore
    dask_local_cluster: LocalCluster,
    minimal_app: FastAPI,
):
    # check it started correctly
    assert minimal_app.state.scheduler_task is not None


@pytest.mark.parametrize(
    "missing_dependency",
    [
        "DIRECTOR_V2_POSTGRES_ENABLED",
        "DIRECTOR_V2_DASK_CLIENT_ENABLED",
    ],
)
def test_scheduler_raises_exception_for_missing_dependencies(
    minimal_dask_scheduler_config: None,
    aiopg_engine: Iterator[aiopg.sa.engine.Engine],  # type: ignore
    dask_local_cluster: LocalCluster,
    monkeypatch: MonkeyPatch,
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


@pytest.fixture
def scheduler(
    minimal_dask_scheduler_config: None,
    aiopg_engine: Iterator[aiopg.sa.engine.Engine],  # type: ignore
    dask_spec_local_cluster: SpecCluster,
    minimal_app: FastAPI,
) -> BaseCompScheduler:
    assert minimal_app.state.scheduler is not None
    return minimal_app.state.scheduler


async def test_empty_pipeline_is_not_scheduled(
    scheduler: BaseCompScheduler,
    minimal_app: FastAPI,
    user_id: PositiveInt,
    project: Callable[..., ProjectAtDB],
    pipeline: Callable[..., CompPipelineAtDB],
    aiopg_engine: Iterator[aiopg.sa.engine.Engine],  # type: ignore
):
    empty_project = project()

    # the project is not in the comp_pipeline, therefore scheduling it should fail
    with pytest.raises(PipelineNotFoundError):
        await scheduler.run_new_pipeline(
            user_id=user_id,
            project_id=empty_project.uuid,
            cluster_id=minimal_app.state.settings.DASK_SCHEDULER.DASK_DEFAULT_CLUSTER_ID,
        )
    # create the empty pipeline now
    _empty_pipeline = pipeline(project_id=f"{empty_project.uuid}")

    # creating a run with an empty pipeline is useless, check the scheduler is not kicking in
    await scheduler.run_new_pipeline(
        user_id=user_id,
        project_id=empty_project.uuid,
        cluster_id=minimal_app.state.settings.DASK_SCHEDULER.DASK_DEFAULT_CLUSTER_ID,
    )
    assert len(scheduler.scheduled_pipelines) == 0
    assert (
        scheduler.wake_up_event.is_set() == False
    ), "the scheduler was woken up on an empty pipeline!"
    # check the database is empty
    async with aiopg_engine.acquire() as conn:  # type: ignore
        result = await conn.scalar(
            comp_runs.select().where(
                (comp_runs.c.user_id == user_id)
                & (comp_runs.c.project_uuid == f"{empty_project.uuid}")
            )  # there is only one entry
        )
        assert result == None


async def test_misconfigured_pipeline_is_not_scheduled(
    scheduler: BaseCompScheduler,
    minimal_app: FastAPI,
    user_id: PositiveInt,
    project: Callable[..., ProjectAtDB],
    pipeline: Callable[..., CompPipelineAtDB],
    fake_workbench_without_outputs: Dict[str, Any],
    fake_workbench_adjacency: Dict[str, Any],
    aiopg_engine: Iterator[aiopg.sa.engine.Engine],  # type: ignore
):
    """A pipeline which comp_tasks are missing should not be scheduled.
    It shall be aborted and shown as such in the comp_runs db"""
    sleepers_project = project(workbench=fake_workbench_without_outputs)
    sleepers_pipeline = pipeline(
        project_id=f"{sleepers_project.uuid}",
        dag_adjacency_list=fake_workbench_adjacency,
    )
    # check the pipeline is correctly added to the scheduled pipelines
    await scheduler.run_new_pipeline(
        user_id=user_id,
        project_id=sleepers_project.uuid,
        cluster_id=minimal_app.state.settings.DASK_SCHEDULER.DASK_DEFAULT_CLUSTER_ID,
    )
    assert len(scheduler.scheduled_pipelines) == 1
    assert (
        scheduler.wake_up_event.is_set() == True
    ), "the scheduler was NOT woken up on the scheduled pipeline!"
    for (u_id, p_id, it), params in scheduler.scheduled_pipelines.items():
        assert u_id == user_id
        assert p_id == sleepers_project.uuid
        assert it > 0
        assert params.mark_for_cancellation == False
    # check the database was properly updated
    async with aiopg_engine.acquire() as conn:  # type: ignore
        result = await conn.execute(
            comp_runs.select().where(
                (comp_runs.c.user_id == user_id)
                & (comp_runs.c.project_uuid == f"{sleepers_project.uuid}")
            )  # there is only one entry
        )
        run_entry = CompRunsAtDB.parse_obj(await result.first())
    assert run_entry.result == RunningState.PUBLISHED
    # let the scheduler kick in
    await asyncio.sleep(1)
    # check the scheduled pipelines is again empty since it's misconfigured
    assert len(scheduler.scheduled_pipelines) == 0
    # check the database entry is correctly updated
    async with aiopg_engine.acquire() as conn:  # type: ignore
        result = await conn.execute(
            comp_runs.select().where(
                (comp_runs.c.user_id == user_id)
                & (comp_runs.c.project_uuid == f"{sleepers_project.uuid}")
            )  # there is only one entry
        )
        run_entry = CompRunsAtDB.parse_obj(await result.first())
    assert run_entry.result == RunningState.ABORTED


async def _assert_comp_run_state(
    aiopg_engine: Iterator[aiopg.sa.engine.Engine],  # type: ignore
    user_id: UserID,
    project_uuid: ProjectID,
    exp_state: RunningState,
):
    # check the database is correctly updated, the run is published
    async with aiopg_engine.acquire() as conn:  # type: ignore
        result = await conn.execute(
            comp_runs.select().where(
                (comp_runs.c.user_id == user_id)
                & (comp_runs.c.project_uuid == f"{project_uuid}")
            )  # there is only one entry
        )
        run_entry = CompRunsAtDB.parse_obj(await result.first())
    assert run_entry.result == exp_state


async def _assert_comp_tasks_state(
    aiopg_engine: Iterator[aiopg.sa.engine.Engine],  # type: ignore
    project_uuid: ProjectID,
    task_ids: List[NodeID],
    exp_state: RunningState,
):
    # check the database is correctly updated, the run is published
    async with aiopg_engine.acquire() as conn:  # type: ignore
        result = await conn.execute(
            comp_tasks.select().where(
                (comp_tasks.c.project_id == f"{project_uuid}")
                & (comp_tasks.c.node_id.in_([f"{n}" for n in task_ids]))
            )  # there is only one entry
        )
        tasks = parse_obj_as(List[CompTaskAtDB], await result.fetchall())
    assert all(  # pylint: disable=use-a-generator
        [t.state == exp_state for t in tasks]
    ), f"expected state: {exp_state}, found: {[t.state for t in tasks]}"


async def _trigger_scheduler(scheduler: BaseCompScheduler):
    # trigger the scheduler
    scheduler._wake_up_scheduler_now()
    await asyncio.sleep(1)


async def _set_task_state(
    aiopg_engine: Iterator[aiopg.sa.engine.Engine], node_id: str, state: StateType  # type: ignore
):
    async with aiopg_engine.acquire() as conn:  # type: ignore
        await conn.execute(
            comp_tasks.update()
            .where(comp_tasks.c.node_id == node_id)
            .values(state=state)
        )


@pytest.fixture
def mocked_dask_client_send_task(mocker: MockerFixture) -> mock.MagicMock:
    mocked_dask_client_send_task = mocker.patch(
        "simcore_service_director_v2.modules.comp_scheduler.dask_scheduler.DaskClient.send_computation_tasks"
    )
    return mocked_dask_client_send_task


@dataclass
class PublishedProject:
    project: ProjectAtDB
    pipeline: CompPipelineAtDB
    tasks: List[CompTaskAtDB]


@pytest.fixture
def published_project(
    project: Callable[..., ProjectAtDB],
    pipeline: Callable[..., CompPipelineAtDB],
    tasks: Callable[..., List[CompTaskAtDB]],
    fake_workbench_without_outputs: Dict[str, Any],
    fake_workbench_adjacency: Dict[str, Any],
) -> PublishedProject:
    created_project = project(workbench=fake_workbench_without_outputs)
    return PublishedProject(
        project=created_project,
        pipeline=pipeline(
            project_id=f"{created_project.uuid}",
            dag_adjacency_list=fake_workbench_adjacency,
        ),
        tasks=tasks(project=created_project, state=RunningState.PUBLISHED),
    )


async def test_proper_pipeline_is_scheduled(
    scheduler: BaseCompScheduler,
    minimal_app: FastAPI,
    user_id: PositiveInt,
    aiopg_engine: Iterator[aiopg.sa.engine.Engine],  # type: ignore
    mocked_dask_client_send_task: mock.MagicMock,
    published_project: PublishedProject,
):
    # This calls adds starts the scheduling of a pipeline
    await scheduler.run_new_pipeline(
        user_id=user_id,
        project_id=published_project.project.uuid,
        cluster_id=minimal_app.state.settings.DASK_SCHEDULER.DASK_DEFAULT_CLUSTER_ID,
    )
    assert len(scheduler.scheduled_pipelines) == 1, "the pipeline is not scheduled!"
    assert (
        scheduler.wake_up_event.is_set() == True
    ), "the scheduler was NOT woken up on the scheduled pipeline!"
    for (u_id, p_id, it), params in scheduler.scheduled_pipelines.items():
        assert u_id == user_id
        assert p_id == published_project.project.uuid
        assert it > 0
        assert params.mark_for_cancellation == False
    # the scheduler automatically kicks in, it should start the 2 first comp tasks
    await asyncio.sleep(1)

    # check the database is correctly updated, the run is published
    await _assert_comp_run_state(
        aiopg_engine,
        user_id,
        published_project.project.uuid,
        exp_state=RunningState.PUBLISHED,
    )
    published_tasks = [
        published_project.tasks[1],
        published_project.tasks[3],
    ]
    # the tasks are set to pending, so they are ready to be taken, and the dask client is triggered
    await _assert_comp_tasks_state(
        aiopg_engine,
        published_project.project.uuid,
        [p.node_id for p in published_tasks],
        exp_state=RunningState.PENDING,
    )
    mocked_dask_client_send_task.assert_has_calls(
        calls=[
            mock.call(
                user_id=user_id,
                project_id=published_project.project.uuid,
                cluster_id=minimal_app.state.settings.DASK_SCHEDULER.DASK_DEFAULT_CLUSTER_ID,
                tasks={f"{p.node_id}": p.image},
                callback=cast(DaskScheduler, scheduler)._on_task_completed,
            )
            for p in published_tasks
        ],
        any_order=True,
    )
    mocked_dask_client_send_task.reset_mock()

    # trigger the scheduler
    await _trigger_scheduler(scheduler)
    # let the scheduler kick in, it should switch to the run state to PENDING state, to reflect the tasks states
    await _assert_comp_run_state(
        aiopg_engine,
        user_id,
        published_project.project.uuid,
        exp_state=RunningState.PENDING,
    )
    # no change here
    await _assert_comp_tasks_state(
        aiopg_engine,
        published_project.project.uuid,
        [p.node_id for p in published_tasks],
        exp_state=RunningState.PENDING,
    )
    mocked_dask_client_send_task.assert_not_called()

    # change 1 task to RUNNING
    running_task_id = published_tasks[0].node_id
    await _set_task_state(
        aiopg_engine,
        node_id=f"{running_task_id}",
        state=StateType.RUNNING,
    )
    # trigger the scheduler, comp_run is now STARTED, as is the task
    await _trigger_scheduler(scheduler)
    await _assert_comp_run_state(
        aiopg_engine, user_id, published_project.project.uuid, RunningState.STARTED
    )
    await _assert_comp_tasks_state(
        aiopg_engine,
        published_project.project.uuid,
        [running_task_id],
        exp_state=RunningState.STARTED,
    )
    mocked_dask_client_send_task.assert_not_called()

    # change the task to SUCCESS
    await _set_task_state(
        aiopg_engine,
        node_id=f"{running_task_id}",
        state=StateType.SUCCESS,
    )
    # trigger the scheduler, the run state is still STARTED, the task is completed
    await _trigger_scheduler(scheduler)
    await _assert_comp_run_state(
        aiopg_engine, user_id, published_project.project.uuid, RunningState.STARTED
    )
    await _assert_comp_tasks_state(
        aiopg_engine,
        published_project.project.uuid,
        [running_task_id],
        exp_state=RunningState.SUCCESS,
    )
    next_published_task = published_project.tasks[2]
    await _assert_comp_tasks_state(
        aiopg_engine,
        published_project.project.uuid,
        [next_published_task.node_id],
        exp_state=RunningState.PENDING,
    )
    mocked_dask_client_send_task.assert_called_once_with(
        user_id=user_id,
        project_id=published_project.project.uuid,
        cluster_id=minimal_app.state.settings.DASK_SCHEDULER.DASK_DEFAULT_CLUSTER_ID,
        tasks={
            f"{next_published_task.node_id}": next_published_task.image,
        },
        callback=cast(DaskScheduler, scheduler)._on_task_completed,
    )
    mocked_dask_client_send_task.reset_mock()

    # change 1 task to RUNNING
    await _set_task_state(
        aiopg_engine,
        node_id=f"{next_published_task.node_id}",
        state=StateType.RUNNING,
    )
    # trigger the scheduler, run state should keep to STARTED, task should be as well
    await _trigger_scheduler(scheduler)
    await _assert_comp_run_state(
        aiopg_engine, user_id, published_project.project.uuid, RunningState.STARTED
    )
    await _assert_comp_tasks_state(
        aiopg_engine,
        published_project.project.uuid,
        [next_published_task.node_id],
        exp_state=RunningState.STARTED,
    )
    mocked_dask_client_send_task.assert_not_called()

    # now change the task to FAILED
    await _set_task_state(
        aiopg_engine,
        node_id=f"{next_published_task.node_id}",
        state=StateType.FAILED,
    )
    # trigger the scheduler, it should keep to STARTED state until it finishes
    await _trigger_scheduler(scheduler)
    await _assert_comp_run_state(
        aiopg_engine, user_id, published_project.project.uuid, RunningState.STARTED
    )
    await _assert_comp_tasks_state(
        aiopg_engine,
        published_project.project.uuid,
        [next_published_task.node_id],
        exp_state=RunningState.FAILED,
    )
    mocked_dask_client_send_task.assert_not_called()

    # now change the other task to SUCCESS
    other_task = published_tasks[1]
    await _set_task_state(
        aiopg_engine,
        node_id=f"{other_task.node_id}",
        state=StateType.SUCCESS,
    )
    # trigger the scheduler, it should switch to FAILED, as we are done
    await _trigger_scheduler(scheduler)
    await _assert_comp_run_state(
        aiopg_engine, user_id, published_project.project.uuid, RunningState.FAILED
    )
    await _assert_comp_tasks_state(
        aiopg_engine,
        published_project.project.uuid,
        [other_task.node_id],
        exp_state=RunningState.SUCCESS,
    )
    mocked_dask_client_send_task.assert_not_called()
    # the scheduled pipeline shall be removed
    assert scheduler.scheduled_pipelines == {}


async def test_handling_of_disconnected_dask_scheduler(
    dask_spec_local_cluster: SpecCluster,
    scheduler: BaseCompScheduler,
    minimal_app: FastAPI,
    user_id: PositiveInt,
    aiopg_engine: Iterator[aiopg.sa.engine.Engine],  # type: ignore
    mocker: MockerFixture,
    published_project: PublishedProject,
):
    # this will crate a non connected backend issue that will trigger re-connection
    mocked_dask_client_send_task = mocker.patch(
        "simcore_service_director_v2.modules.comp_scheduler.dask_scheduler.DaskClient.send_computation_tasks",
        side_effect=ComputationalBackendNotConnectedError(
            msg="faked disconnected backend"
        ),
    )
    mocked_reconnect_client_fct = mocker.patch(
        "simcore_service_director_v2.modules.comp_scheduler.dask_scheduler.DaskClient.reconnect_client"
    )

    # check the pipeline is correctly added to the scheduled pipelines
    await scheduler.run_new_pipeline(
        user_id=user_id,
        project_id=published_project.project.uuid,
        cluster_id=minimal_app.state.settings.DASK_SCHEDULER.DASK_DEFAULT_CLUSTER_ID,
    )
    await _trigger_scheduler(scheduler)
    # since there is no cluster, there is no dask-scheduler,
    # the tasks shall all still be in PUBLISHED state now
    await _assert_comp_run_state(
        aiopg_engine, user_id, published_project.project.uuid, RunningState.PUBLISHED
    )
    # the exception risen should trigger calls to reconnect the client
    mocked_reconnect_client_fct.assert_called()

    # now try to abort the tasks since we are wondering what is happening
    await scheduler.stop_pipeline(
        user_id=user_id, project_id=published_project.project.uuid
    )
    await _trigger_scheduler(scheduler)
    await asyncio.sleep(2)  # to be on the safe side
    await _assert_comp_run_state(
        aiopg_engine, user_id, published_project.project.uuid, RunningState.ABORTED
    )


async def test_completed_task_properly_updates_state(
    scheduler: BaseCompScheduler,
    minimal_app: FastAPI,
    user_id: PositiveInt,
    aiopg_engine: Iterator[aiopg.sa.engine.Engine],  # type: ignore
    mocked_dask_client_send_task: mock.MagicMock,
    published_project: PublishedProject,
):
    # we do have a published project where the comp services are in PUBLISHED state
    # here we will
    ...


async def test_failed_task_cleans_output_files(
    scheduler: BaseCompScheduler,
    minimal_app: FastAPI,
    user_id: PositiveInt,
    aiopg_engine: Iterator[aiopg.sa.engine.Engine],  # type: ignore
    mocked_dask_client_send_task: mock.MagicMock,
    published_project: PublishedProject,
):
    ...
