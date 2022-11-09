# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=no-value-for-parameter
# pylint:disable=protected-access
# pylint:disable=too-many-arguments
# pylint:disable=no-name-in-module
# pylint: disable=too-many-statements


from dataclasses import dataclass
from typing import Any, Callable, Iterator, Union
from unittest import mock

import aiopg
import httpx
import pytest
from _helpers import (
    PublishedProject,
    RunningProject,
    assert_comp_run_state,
    assert_comp_tasks_state,
    manually_run_comp_scheduler,
    set_comp_task_state,
)
from dask.distributed import SpecCluster
from dask_task_models_library.container_tasks.errors import TaskCancelledError
from dask_task_models_library.container_tasks.io import TaskOutputData
from fastapi.applications import FastAPI
from models_library.clusters import DEFAULT_CLUSTER_ID
from models_library.projects import ProjectAtDB
from models_library.projects_state import RunningState
from pytest import MonkeyPatch
from pytest_mock.plugin import MockerFixture
from pytest_simcore.helpers.typing_env import EnvVarsDict
from simcore_postgres_database.models.comp_pipeline import StateType
from simcore_postgres_database.models.comp_runs import comp_runs
from simcore_postgres_database.models.comp_tasks import NodeClass
from simcore_service_director_v2.core.application import init_app
from simcore_service_director_v2.core.errors import (
    ComputationalBackendNotConnectedError,
    ComputationalBackendTaskNotFoundError,
    ComputationalBackendTaskResultsNotReadyError,
    ComputationalSchedulerChangedError,
    ConfigurationError,
    PipelineNotFoundError,
    SchedulerError,
)
from simcore_service_director_v2.core.settings import AppSettings
from simcore_service_director_v2.models.domains.comp_pipelines import CompPipelineAtDB
from simcore_service_director_v2.models.domains.comp_runs import CompRunsAtDB
from simcore_service_director_v2.modules.comp_scheduler import background_task
from simcore_service_director_v2.modules.comp_scheduler.base_scheduler import (
    BaseCompScheduler,
)
from simcore_service_director_v2.utils.scheduler import COMPLETED_STATES
from starlette.testclient import TestClient

pytest_simcore_core_services_selection = [
    "postgres",
]
pytest_simcore_ops_services_selection = [
    "adminer",
]


@pytest.fixture()
def mocked_rabbit_mq_client(mocker: MockerFixture):
    mocker.patch(
        "simcore_service_director_v2.core.application.rabbitmq.RabbitMQClient",
        autospec=True,
    )


@pytest.fixture
def minimal_dask_scheduler_config(
    mock_env: EnvVarsDict,
    postgres_host_config: dict[str, str],
    monkeypatch: MonkeyPatch,
    mocked_rabbit_mq_client: None,
) -> None:
    """set a minimal configuration for testing the dask connection only"""
    monkeypatch.setenv("DIRECTOR_V2_DYNAMIC_SIDECAR_ENABLED", "false")
    monkeypatch.setenv("DIRECTOR_V0_ENABLED", "0")
    monkeypatch.setenv("DIRECTOR_V2_POSTGRES_ENABLED", "1")
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
    aiopg_engine: Iterator[aiopg.sa.engine.Engine],  # type: ignore
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
def mocked_node_ports(mocker: MockerFixture):
    mocker.patch(
        "simcore_service_director_v2.modules.comp_scheduler.dask_scheduler.parse_output_data",
        return_value=None,
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
def mocked_scheduler_task(mocker: MockerFixture) -> None:
    """disables the scheduler task, note that it needs to be triggered manually then"""
    mocker.patch.object(background_task, "scheduler_task")


@pytest.fixture
async def minimal_app(async_client: httpx.AsyncClient) -> FastAPI:
    # must use the minimal app from from the `async_client``
    # the`client` uses starlette's TestClient which spawns
    # a new thread on which it creates a new loop
    # causing issues downstream with coroutines not
    # being created on the same loop
    return async_client._transport.app


async def test_scheduler_gracefully_starts_and_stops(
    minimal_dask_scheduler_config: None,
    aiopg_engine: Iterator[aiopg.sa.engine.Engine],  # type: ignore
    dask_spec_local_cluster: SpecCluster,
    minimal_app: FastAPI,
):
    # check it started correctly
    assert minimal_app.state.scheduler_task is not None


@pytest.mark.parametrize(
    "missing_dependency",
    [
        "DIRECTOR_V2_POSTGRES_ENABLED",
        "COMPUTATIONAL_BACKEND_DASK_CLIENT_ENABLED",
    ],
)
def test_scheduler_raises_exception_for_missing_dependencies(
    minimal_dask_scheduler_config: None,
    aiopg_engine: Iterator[aiopg.sa.engine.Engine],  # type: ignore
    dask_spec_local_cluster: SpecCluster,
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
    mocked_scheduler_task: None,
    scheduler: BaseCompScheduler,
    minimal_app: FastAPI,
    registered_user: Callable[..., dict[str, Any]],
    project: Callable[..., ProjectAtDB],
    pipeline: Callable[..., CompPipelineAtDB],
    aiopg_engine: Iterator[aiopg.sa.engine.Engine],  # type: ignore
):
    user = registered_user()
    empty_project = project(user)

    # the project is not in the comp_pipeline, therefore scheduling it should fail
    with pytest.raises(PipelineNotFoundError):
        await scheduler.run_new_pipeline(
            user_id=user["id"],
            project_id=empty_project.uuid,
            cluster_id=DEFAULT_CLUSTER_ID,
        )
    # create the empty pipeline now
    _empty_pipeline = pipeline(project_id=f"{empty_project.uuid}")

    # creating a run with an empty pipeline is useless, check the scheduler is not kicking in
    await scheduler.run_new_pipeline(
        user_id=user["id"],
        project_id=empty_project.uuid,
        cluster_id=DEFAULT_CLUSTER_ID,
    )
    assert len(scheduler.scheduled_pipelines) == 0
    assert (
        scheduler.wake_up_event.is_set() == False
    ), "the scheduler was woken up on an empty pipeline!"
    # check the database is empty
    async with aiopg_engine.acquire() as conn:  # type: ignore
        result = await conn.scalar(
            comp_runs.select().where(
                (comp_runs.c.user_id == user["id"])
                & (comp_runs.c.project_uuid == f"{empty_project.uuid}")
            )  # there is only one entry
        )
        assert result == None


async def test_misconfigured_pipeline_is_not_scheduled(
    mocked_scheduler_task: None,
    scheduler: BaseCompScheduler,
    minimal_app: FastAPI,
    registered_user: Callable[..., dict[str, Any]],
    project: Callable[..., ProjectAtDB],
    pipeline: Callable[..., CompPipelineAtDB],
    fake_workbench_without_outputs: dict[str, Any],
    fake_workbench_adjacency: dict[str, Any],
    aiopg_engine: Iterator[aiopg.sa.engine.Engine],  # type: ignore
):
    """A pipeline which comp_tasks are missing should not be scheduled.
    It shall be aborted and shown as such in the comp_runs db"""
    user = registered_user()
    sleepers_project = project(user, workbench=fake_workbench_without_outputs)
    sleepers_pipeline = pipeline(
        project_id=f"{sleepers_project.uuid}",
        dag_adjacency_list=fake_workbench_adjacency,
    )
    # check the pipeline is correctly added to the scheduled pipelines
    await scheduler.run_new_pipeline(
        user_id=user["id"],
        project_id=sleepers_project.uuid,
        cluster_id=DEFAULT_CLUSTER_ID,
    )
    assert len(scheduler.scheduled_pipelines) == 1
    assert (
        scheduler.wake_up_event.is_set() == True
    ), "the scheduler was NOT woken up on the scheduled pipeline!"
    for (u_id, p_id, it), params in scheduler.scheduled_pipelines.items():
        assert u_id == user["id"]
        assert p_id == sleepers_project.uuid
        assert it > 0
        assert params.mark_for_cancellation == False
    # check the database was properly updated
    async with aiopg_engine.acquire() as conn:  # type: ignore
        result = await conn.execute(
            comp_runs.select().where(
                (comp_runs.c.user_id == user["id"])
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
                (comp_runs.c.user_id == user["id"])
                & (comp_runs.c.project_uuid == f"{sleepers_project.uuid}")
            )  # there is only one entry
        )
        run_entry = CompRunsAtDB.parse_obj(await result.first())
    assert run_entry.result == RunningState.ABORTED


async def test_proper_pipeline_is_scheduled(
    mocked_scheduler_task: None,
    mocked_dask_client: mock.MagicMock,
    scheduler: BaseCompScheduler,
    minimal_app: FastAPI,
    aiopg_engine: Iterator[aiopg.sa.engine.Engine],  # type: ignore
    published_project: PublishedProject,
):
    # This calls adds starts the scheduling of a pipeline
    await scheduler.run_new_pipeline(
        user_id=published_project.project.prj_owner,
        project_id=published_project.project.uuid,
        cluster_id=DEFAULT_CLUSTER_ID,
    )
    assert len(scheduler.scheduled_pipelines) == 1, "the pipeline is not scheduled!"
    assert (
        scheduler.wake_up_event.is_set() == True
    ), "the scheduler was NOT woken up on the scheduled pipeline!"
    for (u_id, p_id, it), params in scheduler.scheduled_pipelines.items():
        assert u_id == published_project.project.prj_owner
        assert p_id == published_project.project.uuid
        assert it > 0
        assert params.mark_for_cancellation == False
    # check the database is correctly updated, the run is published
    await assert_comp_run_state(
        aiopg_engine,
        published_project.project.prj_owner,
        published_project.project.uuid,
        exp_state=RunningState.PUBLISHED,
    )
    published_tasks = [
        published_project.tasks[1],
        published_project.tasks[3],
    ]
    # trigger the scheduler
    await manually_run_comp_scheduler(scheduler)
    # the client should be created here
    mocked_dask_client.create.assert_called_once_with(
        app=mock.ANY,
        settings=mock.ANY,
        endpoint=mock.ANY,
        authentication=mock.ANY,
        tasks_file_link_type=mock.ANY,
    )
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

    mocked_dask_client.send_computation_tasks.assert_has_calls(
        calls=[
            mock.call(
                published_project.project.prj_owner,
                project_id=published_project.project.uuid,
                cluster_id=DEFAULT_CLUSTER_ID,
                tasks={f"{p.node_id}": p.image},
                callback=scheduler._wake_up_scheduler_now,
            )
            for p in published_tasks
        ],
        any_order=True,
    )
    mocked_dask_client.send_computation_tasks.reset_mock()

    # trigger the scheduler
    await manually_run_comp_scheduler(scheduler)
    # let the scheduler kick in, it should switch to the run state to PENDING state, to reflect the tasks states
    await assert_comp_run_state(
        aiopg_engine,
        published_project.project.prj_owner,
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
    mocked_dask_client.send_computation_tasks.assert_not_called()

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
        aiopg_engine,
        published_project.project.prj_owner,
        published_project.project.uuid,
        RunningState.STARTED,
    )
    await assert_comp_tasks_state(
        aiopg_engine,
        published_project.project.uuid,
        [running_task_id],
        exp_state=RunningState.STARTED,
    )
    mocked_dask_client.send_computation_tasks.assert_not_called()

    # change the task to SUCCESS
    await set_comp_task_state(
        aiopg_engine,
        node_id=f"{running_task_id}",
        state=StateType.SUCCESS,
    )
    # trigger the scheduler, the run state is still STARTED, the task is completed
    await manually_run_comp_scheduler(scheduler)
    await assert_comp_run_state(
        aiopg_engine,
        published_project.project.prj_owner,
        published_project.project.uuid,
        RunningState.STARTED,
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
    mocked_dask_client.send_computation_tasks.assert_called_once_with(
        user_id=published_project.project.prj_owner,
        project_id=published_project.project.uuid,
        cluster_id=DEFAULT_CLUSTER_ID,
        tasks={
            f"{next_published_task.node_id}": next_published_task.image,
        },
        callback=scheduler._wake_up_scheduler_now,
    )
    mocked_dask_client.send_computation_tasks.reset_mock()

    # change 1 task to RUNNING
    await set_comp_task_state(
        aiopg_engine,
        node_id=f"{next_published_task.node_id}",
        state=StateType.RUNNING,
    )
    # trigger the scheduler, run state should keep to STARTED, task should be as well
    await manually_run_comp_scheduler(scheduler)
    await assert_comp_run_state(
        aiopg_engine,
        published_project.project.prj_owner,
        published_project.project.uuid,
        RunningState.STARTED,
    )
    await assert_comp_tasks_state(
        aiopg_engine,
        published_project.project.uuid,
        [next_published_task.node_id],
        exp_state=RunningState.STARTED,
    )
    mocked_dask_client.send_computation_tasks.assert_not_called()

    # now change the task to FAILED
    await set_comp_task_state(
        aiopg_engine,
        node_id=f"{next_published_task.node_id}",
        state=StateType.FAILED,
    )
    # trigger the scheduler, it should keep to STARTED state until it finishes
    await manually_run_comp_scheduler(scheduler)
    await assert_comp_run_state(
        aiopg_engine,
        published_project.project.prj_owner,
        published_project.project.uuid,
        RunningState.STARTED,
    )
    await assert_comp_tasks_state(
        aiopg_engine,
        published_project.project.uuid,
        [next_published_task.node_id],
        exp_state=RunningState.FAILED,
    )
    mocked_dask_client.send_computation_tasks.assert_not_called()

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
        aiopg_engine,
        published_project.project.prj_owner,
        published_project.project.uuid,
        RunningState.FAILED,
    )
    await assert_comp_tasks_state(
        aiopg_engine,
        published_project.project.uuid,
        [other_task.node_id],
        exp_state=RunningState.SUCCESS,
    )
    mocked_dask_client.send_computation_tasks.assert_not_called()
    # the scheduled pipeline shall be removed
    assert scheduler.scheduled_pipelines == {}


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
    mocked_scheduler_task: None,
    dask_spec_local_cluster: SpecCluster,
    scheduler: BaseCompScheduler,
    minimal_app: FastAPI,
    aiopg_engine: Iterator[aiopg.sa.engine.Engine],  # type: ignore
    mocker: MockerFixture,
    published_project: PublishedProject,
    backend_error: SchedulerError,
):
    # this will create a non connected backend issue that will trigger re-connection
    mocked_dask_client_send_task = mocker.patch(
        "simcore_service_director_v2.modules.comp_scheduler.dask_scheduler.DaskClient.send_computation_tasks",
        side_effect=backend_error,
    )

    # running the pipeline will now raise and the tasks are set back to PUBLISHED
    await scheduler.run_new_pipeline(
        user_id=published_project.project.prj_owner,
        project_id=published_project.project.uuid,
        cluster_id=DEFAULT_CLUSTER_ID,
    )

    # since there is no cluster, there is no dask-scheduler,
    # the tasks shall all still be in PUBLISHED state now
    await assert_comp_run_state(
        aiopg_engine,
        published_project.project.prj_owner,
        published_project.project.uuid,
        RunningState.PUBLISHED,
    )
    await assert_comp_tasks_state(
        aiopg_engine,
        published_project.project.uuid,
        [t.node_id for t in published_project.tasks],
        exp_state=RunningState.PUBLISHED,
    )
    # on the next iteration of the pipeline it will try to re-connect
    # now try to abort the tasks since we are wondering what is happening, this should auto-trigger the scheduler
    await scheduler.stop_pipeline(
        user_id=published_project.project.prj_owner,
        project_id=published_project.project.uuid,
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
        aiopg_engine,
        published_project.project.prj_owner,
        published_project.project.uuid,
        RunningState.ABORTED,
    )


@dataclass
class RebootState:
    task_status: RunningState
    task_result: Union[Exception, TaskOutputData]
    expected_task_state_group1: RunningState
    expected_task_state_group2: RunningState
    expected_run_state: RunningState


@pytest.mark.parametrize(
    "reboot_state",
    [
        pytest.param(
            RebootState(
                RunningState.UNKNOWN,
                ComputationalBackendTaskNotFoundError(job_id="fake_job_id"),
                RunningState.FAILED,
                RunningState.ABORTED,
                RunningState.FAILED,
            ),
            id="reboot with lost tasks",
        ),
        pytest.param(
            RebootState(
                RunningState.ABORTED,
                TaskCancelledError(job_id="fake_job_id"),
                RunningState.ABORTED,
                RunningState.ABORTED,
                RunningState.ABORTED,
            ),
            id="reboot with aborted tasks",
        ),
        pytest.param(
            RebootState(
                RunningState.FAILED,
                ValueError("some error during the call"),
                RunningState.FAILED,
                RunningState.ABORTED,
                RunningState.FAILED,
            ),
            id="reboot with failed tasks",
        ),
        pytest.param(
            RebootState(
                RunningState.STARTED,
                ComputationalBackendTaskResultsNotReadyError(job_id="fake_job_id"),
                RunningState.STARTED,
                RunningState.STARTED,
                RunningState.STARTED,
            ),
            id="reboot with running tasks",
        ),
        pytest.param(
            RebootState(
                RunningState.SUCCESS,
                TaskOutputData.parse_obj({"whatever_output": 123}),
                RunningState.SUCCESS,
                RunningState.SUCCESS,
                RunningState.SUCCESS,
            ),
            id="reboot with completed tasks",
        ),
    ],
)
async def test_handling_scheduling_after_reboot(
    mocked_scheduler_task: None,
    mocked_dask_client: mock.MagicMock,
    aiopg_engine: aiopg.sa.engine.Engine,  # type: ignore
    running_project: RunningProject,
    scheduler: BaseCompScheduler,
    minimal_app: FastAPI,
    mocked_node_ports: None,
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

    await manually_run_comp_scheduler(scheduler)
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

    await assert_comp_tasks_state(
        aiopg_engine,
        running_project.project.uuid,
        [
            running_project.tasks[1].node_id,
            running_project.tasks[2].node_id,
            running_project.tasks[3].node_id,
        ],
        exp_state=reboot_state.expected_task_state_group1,
    )
    await assert_comp_tasks_state(
        aiopg_engine,
        running_project.project.uuid,
        [running_project.tasks[4].node_id],
        exp_state=reboot_state.expected_task_state_group2,
    )
    await assert_comp_run_state(
        aiopg_engine,
        running_project.project.prj_owner,
        running_project.project.uuid,
        exp_state=reboot_state.expected_run_state,
    )
