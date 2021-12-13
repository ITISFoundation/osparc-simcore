# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=no-value-for-parameter
# pylint:disable=protected-access
# pylint:disable=too-many-arguments
# pylint:disable=no-name-in-module

from typing import Any, Callable, Dict, Iterator, cast
from unittest import mock

import aiopg
import pytest
from _helpers import PublishedProject  # type: ignore
from _helpers import assert_comp_run_state  # type: ignore
from _helpers import assert_comp_tasks_state  # type: ignore
from _helpers import manually_run_comp_scheduler  # type: ignore
from _helpers import set_comp_task_state  # type: ignore
from _pytest.monkeypatch import MonkeyPatch
from dask.distributed import LocalCluster, SpecCluster
from dask_task_models_library.container_tasks.events import TaskStateEvent
from dask_task_models_library.container_tasks.io import TaskOutputData
from fastapi.applications import FastAPI
from models_library.projects import ProjectAtDB
from models_library.projects_state import RunningState
from pydantic import PositiveInt
from pytest_mock.plugin import MockerFixture
from simcore_postgres_database.models.comp_pipeline import StateType
from simcore_postgres_database.models.comp_runs import comp_runs
from simcore_postgres_database.models.comp_tasks import NodeClass
from simcore_service_director_v2.core.application import init_app
from simcore_service_director_v2.core.errors import (
    ComputationalBackendNotConnectedError,
    ConfigurationError,
    PipelineNotFoundError,
)
from simcore_service_director_v2.core.settings import AppSettings
from simcore_service_director_v2.models.domains.comp_pipelines import CompPipelineAtDB
from simcore_service_director_v2.models.domains.comp_runs import CompRunsAtDB
from simcore_service_director_v2.modules.comp_scheduler import background_task
from simcore_service_director_v2.modules.comp_scheduler.base_scheduler import (
    BaseCompScheduler,
)
from simcore_service_director_v2.modules.comp_scheduler.dask_scheduler import (
    DaskScheduler,
)
from simcore_service_director_v2.utils.dask import generate_dask_job_id
from simcore_service_director_v2.utils.scheduler import COMPLETED_STATES
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


@pytest.fixture
def scheduler(
    minimal_dask_scheduler_config: None,
    aiopg_engine: Iterator[aiopg.sa.engine.Engine],  # type: ignore
    dask_spec_local_cluster: SpecCluster,
    minimal_app: FastAPI,
) -> BaseCompScheduler:
    assert minimal_app.state.scheduler is not None
    return minimal_app.state.scheduler


@pytest.fixture
def mocked_dask_client_send_task(mocker: MockerFixture) -> mock.MagicMock:
    mocked_dask_client_send_task = mocker.patch(
        "simcore_service_director_v2.modules.comp_scheduler.dask_scheduler.DaskClient.send_computation_tasks"
    )
    return mocked_dask_client_send_task


@pytest.fixture
def mocked_node_ports(mocker: MockerFixture):
    mocker.patch(
        "simcore_service_director_v2.modules.comp_scheduler.dask_scheduler.parse_output_data",
        return_value=None,
    )


@pytest.fixture
def mocked_clean_task_output_fct(mocker: MockerFixture) -> mock.MagicMock:
    return mocker.patch(
        "simcore_service_director_v2.modules.comp_scheduler.dask_scheduler.clean_task_output_and_log_files_if_invalid",
        return_value=None,
    )


@pytest.fixture
def mocked_scheduler_task(monkeypatch: MonkeyPatch) -> None:
    async def mocked_scheduler_task(app: FastAPI) -> None:
        return None

    monkeypatch.setattr(background_task, "scheduler_task", mocked_scheduler_task)


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


async def test_empty_pipeline_is_not_scheduled(
    scheduler: BaseCompScheduler,
    minimal_app: FastAPI,
    user_id: PositiveInt,
    project: Callable[..., ProjectAtDB],
    pipeline: Callable[..., CompPipelineAtDB],
    aiopg_engine: Iterator[aiopg.sa.engine.Engine],  # type: ignore
    mocked_scheduler_task: None,
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
    mocked_scheduler_task: None,
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
    await manually_run_comp_scheduler(scheduler)
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


async def test_proper_pipeline_is_scheduled(
    scheduler: BaseCompScheduler,
    minimal_app: FastAPI,
    user_id: PositiveInt,
    aiopg_engine: Iterator[aiopg.sa.engine.Engine],  # type: ignore
    mocked_dask_client_send_task: mock.MagicMock,
    published_project: PublishedProject,
    mocked_scheduler_task: None,
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
    # check the database is correctly updated, the run is published
    await assert_comp_run_state(
        aiopg_engine,
        user_id,
        published_project.project.uuid,
        exp_state=RunningState.PUBLISHED,
    )
    published_tasks = [
        published_project.tasks[1],
        published_project.tasks[3],
    ]
    # trigger the scheduler
    await manually_run_comp_scheduler(scheduler)
    # the tasks are set to pending, so they are ready to be taken, and the dask client is triggered
    await assert_comp_tasks_state(
        aiopg_engine,
        published_project.project.uuid,
        [p.node_id for p in published_tasks],
        exp_state=RunningState.PENDING,
    )
    # the other tasks are published
    await assert_comp_tasks_state(
        aiopg_engine,
        published_project.project.uuid,
        [p.node_id for p in published_project.tasks if p not in published_tasks],
        exp_state=RunningState.PUBLISHED,
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
    await manually_run_comp_scheduler(scheduler)
    # let the scheduler kick in, it should switch to the run state to PENDING state, to reflect the tasks states
    await assert_comp_run_state(
        aiopg_engine,
        user_id,
        published_project.project.uuid,
        exp_state=RunningState.PENDING,
    )
    # no change here
    await assert_comp_tasks_state(
        aiopg_engine,
        published_project.project.uuid,
        [p.node_id for p in published_tasks],
        exp_state=RunningState.PENDING,
    )
    mocked_dask_client_send_task.assert_not_called()

    # change 1 task to RUNNING
    running_task_id = published_tasks[0].node_id
    await set_comp_task_state(
        aiopg_engine,
        node_id=f"{running_task_id}",
        state=StateType.RUNNING,
    )
    # trigger the scheduler, comp_run is now STARTED, as is the task
    await manually_run_comp_scheduler(scheduler)
    await assert_comp_run_state(
        aiopg_engine, user_id, published_project.project.uuid, RunningState.STARTED
    )
    await assert_comp_tasks_state(
        aiopg_engine,
        published_project.project.uuid,
        [running_task_id],
        exp_state=RunningState.STARTED,
    )
    mocked_dask_client_send_task.assert_not_called()

    # change the task to SUCCESS
    await set_comp_task_state(
        aiopg_engine,
        node_id=f"{running_task_id}",
        state=StateType.SUCCESS,
    )
    # trigger the scheduler, the run state is still STARTED, the task is completed
    await manually_run_comp_scheduler(scheduler)
    await assert_comp_run_state(
        aiopg_engine, user_id, published_project.project.uuid, RunningState.STARTED
    )
    await assert_comp_tasks_state(
        aiopg_engine,
        published_project.project.uuid,
        [running_task_id],
        exp_state=RunningState.SUCCESS,
    )
    next_published_task = published_project.tasks[2]
    await assert_comp_tasks_state(
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
    await set_comp_task_state(
        aiopg_engine,
        node_id=f"{next_published_task.node_id}",
        state=StateType.RUNNING,
    )
    # trigger the scheduler, run state should keep to STARTED, task should be as well
    await manually_run_comp_scheduler(scheduler)
    await assert_comp_run_state(
        aiopg_engine, user_id, published_project.project.uuid, RunningState.STARTED
    )
    await assert_comp_tasks_state(
        aiopg_engine,
        published_project.project.uuid,
        [next_published_task.node_id],
        exp_state=RunningState.STARTED,
    )
    mocked_dask_client_send_task.assert_not_called()

    # now change the task to FAILED
    await set_comp_task_state(
        aiopg_engine,
        node_id=f"{next_published_task.node_id}",
        state=StateType.FAILED,
    )
    # trigger the scheduler, it should keep to STARTED state until it finishes
    await manually_run_comp_scheduler(scheduler)
    await assert_comp_run_state(
        aiopg_engine, user_id, published_project.project.uuid, RunningState.STARTED
    )
    await assert_comp_tasks_state(
        aiopg_engine,
        published_project.project.uuid,
        [next_published_task.node_id],
        exp_state=RunningState.FAILED,
    )
    mocked_dask_client_send_task.assert_not_called()

    # now change the other task to SUCCESS
    other_task = published_tasks[1]
    await set_comp_task_state(
        aiopg_engine,
        node_id=f"{other_task.node_id}",
        state=StateType.SUCCESS,
    )
    # trigger the scheduler, it should switch to FAILED, as we are done
    await manually_run_comp_scheduler(scheduler)
    await assert_comp_run_state(
        aiopg_engine, user_id, published_project.project.uuid, RunningState.FAILED
    )
    await assert_comp_tasks_state(
        aiopg_engine,
        published_project.project.uuid,
        [other_task.node_id],
        exp_state=RunningState.SUCCESS,
    )
    mocked_dask_client_send_task.assert_not_called()
    # the scheduled pipeline shall be removed
    assert scheduler.scheduled_pipelines == {}


async def test_handling_of_disconnected_dask_scheduler(
    mocked_scheduler_task: None,
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
    # mocked_delete_client_fct = mocker.patch(
    #     "simcore_service_director_v2.modules.comp_scheduler.dask_scheduler.DaskClient.delete",
    #     autospec=True,
    # )

    # check the pipeline is correctly added to the scheduled pipelines
    await scheduler.run_new_pipeline(
        user_id=user_id,
        project_id=published_project.project.uuid,
        cluster_id=minimal_app.state.settings.DASK_SCHEDULER.DASK_DEFAULT_CLUSTER_ID,
    )
    with pytest.raises(ComputationalBackendNotConnectedError):
        await manually_run_comp_scheduler(scheduler)

    # since there is no cluster, there is no dask-scheduler,
    # the tasks shall all still be in PUBLISHED state now
    await assert_comp_run_state(
        aiopg_engine, user_id, published_project.project.uuid, RunningState.PUBLISHED
    )
    await assert_comp_tasks_state(
        aiopg_engine,
        published_project.project.uuid,
        [t.node_id for t in published_project.tasks],
        exp_state=RunningState.PUBLISHED,
    )
    # the exception risen should trigger calls to reconnect the client, we do it manually here
    old_dask_client = cast(DaskScheduler, scheduler).dask_client
    await scheduler.reconnect_backend()
    # this will delete and re-create the dask client
    new_dask_client = cast(DaskScheduler, scheduler).dask_client
    assert old_dask_client is not new_dask_client

    # now try to abort the tasks since we are wondering what is happening, this should auto-trigger the scheduler
    await scheduler.stop_pipeline(
        user_id=user_id, project_id=published_project.project.uuid
    )
    # we ensure the scheduler was run
    await manually_run_comp_scheduler(scheduler)
    # after this step the tasks are marked as ABORTED
    await assert_comp_tasks_state(
        aiopg_engine,
        published_project.project.uuid,
        [
            t.node_id
            for t in published_project.tasks
            if t.node_class == NodeClass.COMPUTATIONAL
        ],
        exp_state=RunningState.ABORTED,
    )
    # then we have another scheduler run
    await manually_run_comp_scheduler(scheduler)
    # now the run should be ABORTED
    await assert_comp_run_state(
        aiopg_engine, user_id, published_project.project.uuid, RunningState.ABORTED
    )


@pytest.mark.parametrize("state", COMPLETED_STATES)
async def test_completed_task_properly_updates_state(
    scheduler: BaseCompScheduler,
    minimal_app: FastAPI,
    user_id: PositiveInt,
    aiopg_engine: Iterator[aiopg.sa.engine.Engine],  # type: ignore
    published_project: PublishedProject,
    mocked_node_ports: None,
    mocked_clean_task_output_fct: mock.MagicMock,
    state: RunningState,
    mocked_scheduler_task: None,
):
    # we do have a published project where the comp services are in PUBLISHED state
    # here we will artifically call the completion handler in the scheduler
    dask_scheduler = cast(DaskScheduler, scheduler)
    job_id = generate_dask_job_id(
        "simcore/service/comp/pytest/fake",
        "12.34.55",
        user_id,
        published_project.project.uuid,
        published_project.tasks[0].node_id,
    )
    state_event = TaskStateEvent(
        job_id=job_id,
        msg=TaskOutputData.parse_obj({"output_1": "some fake data"}).json(),
        state=state,
    )
    await dask_scheduler._on_task_completed(state_event)
    await assert_comp_tasks_state(
        aiopg_engine,
        published_project.project.uuid,
        [published_project.tasks[0].node_id],
        exp_state=state,
    )


@pytest.mark.parametrize("state", [RunningState.ABORTED, RunningState.FAILED])
async def test_failed_or_aborted_task_cleans_output_files(
    scheduler: BaseCompScheduler,
    minimal_app: FastAPI,
    user_id: PositiveInt,
    aiopg_engine: Iterator[aiopg.sa.engine.Engine],  # type: ignore
    mocked_dask_client_send_task: mock.MagicMock,
    published_project: PublishedProject,
    state: RunningState,
    mocked_clean_task_output_fct: mock.MagicMock,
    mocked_scheduler_task: None,
):
    # we do have a published project where the comp services are in PUBLISHED state
    # here we will artifically call the completion handler in the scheduler
    dask_scheduler = cast(DaskScheduler, scheduler)
    job_id = generate_dask_job_id(
        "simcore/service/comp/pytest/fake",
        "12.34.55",
        user_id,
        published_project.project.uuid,
        published_project.tasks[0].node_id,
    )
    state_event = TaskStateEvent(
        job_id=job_id,
        msg=TaskOutputData.parse_obj({"output_1": "some fake data"}).json(),
        state=state,
    )
    await dask_scheduler._on_task_completed(state_event)
    await assert_comp_tasks_state(
        aiopg_engine,
        published_project.project.uuid,
        [published_project.tasks[0].node_id],
        exp_state=state,
    )

    mocked_clean_task_output_fct.assert_called_once()
