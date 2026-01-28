"""The scheduler shall be run as a background task.
Based on oSparc pipelines, it monitors when to start the next worker task(s), either one at a time or as a group of tasks.

In principle the Scheduler maintains the comp_runs table in the database.
It contains how the pipeline was run and by whom.
It also contains the final result of the pipeline run.

When a pipeline is scheduled first all the tasks contained in the DAG are set to PUBLISHED state.
Once the scheduler determines a task shall run, its state is set to PENDING, so that the sidecar can pick up the task.
The sidecar will then change the state to STARTED, then to SUCCESS or FAILED.

"""

import asyncio
import datetime
import logging
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from typing import Final

import arrow
import networkx as nx
from common_library.logging.logging_errors import create_troubleshooting_log_kwargs
from common_library.user_messages import user_message
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID, NodeIDStr
from models_library.projects_state import RunningState
from models_library.services import ServiceType
from models_library.services_types import ServiceRunID
from models_library.users import UserID
from networkx.classes.reportviews import InDegreeView
from pydantic import PositiveInt
from servicelib.common_headers import UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE
from servicelib.logging_utils import log_catch, log_context
from servicelib.rabbitmq import RabbitMQClient, RabbitMQRPCClient
from servicelib.redis import RedisClientSDK
from servicelib.utils import limited_gather
from sqlalchemy.ext.asyncio import AsyncEngine

from ...constants import UNDEFINED_STR_METADATA
from ...core.errors import (
    ClustersKeeperNotAvailableError,
    ComputationalBackendNotConnectedError,
    ComputationalBackendOnDemandNotReadyError,
    ComputationalSchedulerChangedError,
    DaskClientAcquisisitonError,
    InvalidPipelineError,
    PipelineNotFoundError,
)
from ...core.settings import ComputationalBackendSettings
from ...models.comp_pipelines import CompPipelineAtDB
from ...models.comp_runs import CompRunsAtDB, Iteration, RunMetadataDict
from ...models.comp_tasks import CompTaskAtDB
from ...utils.computations import get_pipeline_state_from_task_states
from ...utils.rabbitmq import (
    publish_pipeline_scheduling_state,
    publish_project_log,
    publish_service_resource_tracking_heartbeat,
    publish_service_resource_tracking_started,
    publish_service_started_metrics,
)
from ..db.repositories.comp_pipelines import CompPipelinesRepository
from ..db.repositories.comp_runs import CompRunsRepository
from ..db.repositories.comp_tasks import CompTasksRepository
from ._models import TaskStateTracker
from ._publisher import request_pipeline_scheduling
from ._utils import (
    COMPLETED_STATES,
    PROCESSING_STATES,
    RUNNING_STATES,
    TASK_TO_START_STATES,
    WAITING_FOR_START_STATES,
    create_service_resources_from_task,
)

_logger = logging.getLogger(__name__)


_MAX_WAITING_TIME_FOR_UNKNOWN_TASKS: Final[datetime.timedelta] = datetime.timedelta(seconds=30)
_PUBLICATION_CONCURRENCY_LIMIT: Final[int] = 10


def _auto_schedule_callback(
    loop: asyncio.AbstractEventLoop,
    db_engine: AsyncEngine,
    rabbit_mq_client: RabbitMQClient,
    *,
    user_id: UserID,
    project_id: ProjectID,
    iteration: Iteration,
) -> Callable[[], None]:
    """this function is called via Dask-backend from a separate thread.
    Therefore the need to use run_coroutine_threadsafe to request a new
    pipeline scheduling"""

    def _cb() -> None:
        async def _async_cb() -> None:
            await request_pipeline_scheduling(
                rabbit_mq_client,
                db_engine,
                user_id=user_id,
                project_id=project_id,
                iteration=iteration,
            )

        future = asyncio.run_coroutine_threadsafe(_async_cb(), loop)
        with log_catch(_logger, reraise=False):
            future.result(timeout=10)

    return _cb


@dataclass(frozen=True, slots=True)
class SortedTasks:
    started: list[CompTaskAtDB]
    completed: list[TaskStateTracker]
    waiting: list[TaskStateTracker]
    potentially_lost: list[TaskStateTracker]


async def _triage_changed_tasks(
    changed_tasks: list[TaskStateTracker],
) -> SortedTasks:
    started_tasks = [
        tracker.current
        for tracker in changed_tasks
        if tracker.current.state in RUNNING_STATES
        or (tracker.previous.state in WAITING_FOR_START_STATES and tracker.current.state in COMPLETED_STATES)
    ]

    completed_tasks = [tracker for tracker in changed_tasks if tracker.current.state in COMPLETED_STATES]

    waiting_for_resources_tasks = [
        tracker for tracker in changed_tasks if tracker.current.state in WAITING_FOR_START_STATES
    ]

    lost_tasks = [
        tracker
        for tracker in changed_tasks
        if (tracker.current.state is RunningState.UNKNOWN)
        and ((arrow.utcnow().datetime - tracker.previous.modified) > _MAX_WAITING_TIME_FOR_UNKNOWN_TASKS)
    ]
    if lost_tasks:
        _logger.warning(
            "%s are currently in unknown state. TIP: If they are running in an external cluster and it is not yet ready, that might explain it. But inform @sanderegg nevertheless!",
            [t.current.node_id for t in lost_tasks],
        )

    return SortedTasks(
        started_tasks,
        completed_tasks,
        waiting_for_resources_tasks,
        lost_tasks,
    )


@dataclass
class BaseCompScheduler(ABC):
    db_engine: AsyncEngine
    rabbitmq_client: RabbitMQClient
    rabbitmq_rpc_client: RabbitMQRPCClient
    settings: ComputationalBackendSettings
    service_runtime_heartbeat_interval: datetime.timedelta
    redis_client: RedisClientSDK

    async def _get_pipeline_dag(self, project_id: ProjectID) -> nx.DiGraph:
        comp_pipeline_repo = CompPipelinesRepository.instance(self.db_engine)
        pipeline_at_db: CompPipelineAtDB = await comp_pipeline_repo.get_pipeline(project_id)
        dag = pipeline_at_db.get_graph()
        _logger.debug("%s: current %s", f"{project_id=}", f"{dag=}")
        return dag

    async def _get_pipeline_tasks(
        self, project_id: ProjectID, pipeline_dag: nx.DiGraph
    ) -> dict[NodeIDStr, CompTaskAtDB]:
        comp_tasks_repo = CompTasksRepository.instance(self.db_engine)
        pipeline_comp_tasks: dict[NodeIDStr, CompTaskAtDB] = {
            f"{t.node_id}": t
            for t in await comp_tasks_repo.list_computational_tasks(project_id)
            if (f"{t.node_id}" in list(pipeline_dag.nodes()))
        }
        if len(pipeline_comp_tasks) != len(pipeline_dag.nodes()):
            msg = (
                f"The tasks defined for {project_id} do not contain all"
                f" the tasks defined in the pipeline [{list(pipeline_dag.nodes)}]! Please check."
            )
            raise InvalidPipelineError(pipeline_id=project_id, msg=msg)
        return pipeline_comp_tasks

    async def _update_run_result_from_tasks(
        self,
        user_id: UserID,
        project_id: ProjectID,
        iteration: Iteration,
        pipeline_tasks: dict[NodeIDStr, CompTaskAtDB],
        current_result: RunningState,
    ) -> RunningState:
        pipeline_state_from_tasks = get_pipeline_state_from_task_states(
            list(pipeline_tasks.values()),
        )
        if pipeline_state_from_tasks == current_result:
            return pipeline_state_from_tasks
        _logger.debug(
            "pipeline %s is currently in %s",
            f"{user_id=}_{project_id=}_{iteration=}",
            f"{pipeline_state_from_tasks}",
        )
        await self._set_run_result(user_id, project_id, iteration, pipeline_state_from_tasks)
        return pipeline_state_from_tasks

    async def _set_run_result(
        self,
        user_id: UserID,
        project_id: ProjectID,
        iteration: Iteration,
        run_result: RunningState,
    ) -> None:
        comp_runs_repo = CompRunsRepository.instance(self.db_engine)
        await comp_runs_repo.set_run_result(
            user_id=user_id,
            project_id=project_id,
            iteration=iteration,
            result_state=run_result,
            final_state=(run_result in COMPLETED_STATES),
        )

        if run_result in COMPLETED_STATES:
            # send event to notify the piipeline is done
            await publish_project_log(
                self.rabbitmq_client,
                user_id=user_id,
                project_id=project_id,
                log=user_message(
                    f"Project pipeline execution for iteration {iteration} has completed with status: {run_result.value}",
                    _version=1,
                ),
                log_level=logging.INFO,
            )
        await publish_pipeline_scheduling_state(self.rabbitmq_client, user_id, project_id, run_result)

    async def _set_processing_done(
        self,
        user_id: UserID,
        project_id: ProjectID,
        iteration: Iteration,
    ) -> None:
        with log_context(
            _logger,
            logging.DEBUG,
            msg=f"mark pipeline run for {iteration=} for {user_id=} and {project_id=} as processed",
        ):
            await CompRunsRepository.instance(self.db_engine).mark_as_processed(
                user_id=user_id,
                project_id=project_id,
                iteration=iteration,
            )

    async def _set_states_following_failed_to_aborted(
        self,
        project_id: ProjectID,
        dag: nx.DiGraph,
        tasks: dict[NodeIDStr, CompTaskAtDB],
        run_id: PositiveInt,
    ) -> dict[NodeIDStr, CompTaskAtDB]:
        # Perform a reverse topological sort to ensure tasks are ordered from last to first
        sorted_node_ids = list(reversed(list(nx.topological_sort(dag))))
        tasks = {node_id: tasks[node_id] for node_id in sorted_node_ids if node_id in tasks}
        # we need the tasks ordered from the last task to the first
        node_ids_to_set_as_aborted: set[NodeIDStr] = set()
        for task in tasks.values():
            if task.state == RunningState.FAILED:
                node_ids_to_set_as_aborted.update(nx.bfs_tree(dag, f"{task.node_id}"))
                node_ids_to_set_as_aborted.remove(f"{task.node_id}")
        for node_id in node_ids_to_set_as_aborted:
            tasks[f"{node_id}"].state = RunningState.ABORTED
        if node_ids_to_set_as_aborted:
            # update the current states back in DB
            comp_tasks_repo = CompTasksRepository.instance(self.db_engine)
            await comp_tasks_repo.update_project_tasks_state(
                project_id,
                run_id,
                [NodeID(n) for n in node_ids_to_set_as_aborted],
                RunningState.ABORTED,
                optional_progress=1.0,
                optional_stopped=arrow.utcnow().datetime,
            )
        return tasks

    async def _send_running_tasks_heartbeat(
        self,
        user_id: UserID,
        project_id: ProjectID,
        run_id: PositiveInt,
        iteration: Iteration,
        dag: nx.DiGraph,
    ) -> None:
        utc_now = arrow.utcnow().datetime

        def _need_heartbeat(task: CompTaskAtDB) -> bool:
            if task.state not in RUNNING_STATES:
                return False

            if task.last_heartbeat is None:
                assert task.start  # nosec
                return bool(
                    (utc_now - task.start.replace(tzinfo=datetime.UTC)) > self.service_runtime_heartbeat_interval
                )
            return bool((utc_now - task.last_heartbeat) > self.service_runtime_heartbeat_interval)

        tasks: dict[NodeIDStr, CompTaskAtDB] = await self._get_pipeline_tasks(project_id, dag)
        if running_tasks := [t for t in tasks.values() if _need_heartbeat(t)]:
            await limited_gather(
                *(
                    publish_service_resource_tracking_heartbeat(
                        self.rabbitmq_client,
                        ServiceRunID.get_resource_tracking_run_id_for_computational(
                            user_id, t.project_id, t.node_id, iteration
                        ),
                    )
                    for t in running_tasks
                ),
                log=_logger,
                limit=_PUBLICATION_CONCURRENCY_LIMIT,
            )
            comp_tasks_repo = CompTasksRepository.instance(self.db_engine)
            for task in running_tasks:
                await comp_tasks_repo.update_project_task_last_heartbeat(project_id, task.node_id, run_id, utc_now)

    async def _get_changed_tasks_from_backend(
        self,
        user_id: UserID,
        processing_tasks: list[CompTaskAtDB],
        comp_run: CompRunsAtDB,
    ) -> tuple[list[TaskStateTracker], list[CompTaskAtDB]]:
        tasks_backend_status = await self._get_tasks_status(user_id, processing_tasks, comp_run)

        return (
            [
                TaskStateTracker(
                    task,
                    task.model_copy(update={"state": backend_state}),
                )
                for task, backend_state in zip(processing_tasks, tasks_backend_status, strict=True)
                if task.state is not backend_state
            ],
            [
                task
                for task, backend_state in zip(processing_tasks, tasks_backend_status, strict=True)
                if task.state is backend_state is RunningState.STARTED
            ],
        )

    async def _process_started_tasks(
        self,
        tasks: list[CompTaskAtDB],
        *,
        user_id: UserID,
        project_id: ProjectID,
        iteration: Iteration,
        run_metadata: RunMetadataDict,
        run_id: PositiveInt,
    ) -> None:
        utc_now = arrow.utcnow().datetime

        # resource tracking
        await limited_gather(
            *(
                publish_service_resource_tracking_started(
                    self.rabbitmq_client,
                    service_run_id=ServiceRunID.get_resource_tracking_run_id_for_computational(
                        user_id, t.project_id, t.node_id, iteration
                    ),
                    wallet_id=run_metadata.get("wallet_id"),
                    wallet_name=run_metadata.get("wallet_name"),
                    pricing_plan_id=(t.pricing_info.get("pricing_plan_id") if t.pricing_info else None),
                    pricing_unit_id=(t.pricing_info.get("pricing_unit_id") if t.pricing_info else None),
                    pricing_unit_cost_id=(t.pricing_info.get("pricing_unit_cost_id") if t.pricing_info else None),
                    product_name=run_metadata.get("product_name", UNDEFINED_STR_METADATA),
                    simcore_user_agent=run_metadata.get(
                        "simcore_user_agent", UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE
                    ),
                    user_id=user_id,
                    user_email=run_metadata.get("user_email", UNDEFINED_STR_METADATA),
                    project_id=t.project_id,
                    project_name=run_metadata.get("project_name", UNDEFINED_STR_METADATA),
                    node_id=t.node_id,
                    node_name=run_metadata.get("node_id_names_map", {}).get(t.node_id, UNDEFINED_STR_METADATA),
                    parent_project_id=run_metadata.get("project_metadata", {}).get("parent_project_id"),
                    parent_node_id=run_metadata.get("project_metadata", {}).get("parent_node_id"),
                    root_parent_project_id=run_metadata.get("project_metadata", {}).get("root_parent_project_id"),
                    root_parent_project_name=run_metadata.get("project_metadata", {}).get("root_parent_project_name"),
                    root_parent_node_id=run_metadata.get("project_metadata", {}).get("root_parent_node_id"),
                    service_key=t.image.name,
                    service_version=t.image.tag,
                    service_type=ServiceType.COMPUTATIONAL,
                    service_resources=create_service_resources_from_task(t),
                    service_additional_metadata={},
                )
                for t in tasks
            ),
            log=_logger,
            limit=_PUBLICATION_CONCURRENCY_LIMIT,
        )
        # instrumentation
        await limited_gather(
            *(
                publish_service_started_metrics(
                    self.rabbitmq_client,
                    user_id=user_id,
                    simcore_user_agent=run_metadata.get(
                        "simcore_user_agent", UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE
                    ),
                    task=t,
                )
                for t in tasks
            ),
            log=_logger,
            limit=_PUBLICATION_CONCURRENCY_LIMIT,
        )

        # update DB
        comp_tasks_repo = CompTasksRepository(self.db_engine)
        for task in tasks:
            await comp_tasks_repo.update_project_tasks_state(
                project_id,
                run_id,
                [task.node_id],
                task.state,
                optional_started=utc_now,
                optional_progress=task.progress,
            )
        await CompRunsRepository.instance(self.db_engine).mark_as_started(
            user_id=user_id,
            project_id=project_id,
            iteration=iteration,
            started_time=utc_now,
        )

    async def _process_waiting_tasks(self, tasks: list[TaskStateTracker], run_id: PositiveInt) -> None:
        comp_tasks_repo = CompTasksRepository.instance(self.db_engine)
        for task in tasks:
            await comp_tasks_repo.update_project_tasks_state(
                task.current.project_id,
                run_id,
                [task.current.node_id],
                task.current.state,
            )

    async def _update_states_from_comp_backend(
        self,
        user_id: UserID,
        project_id: ProjectID,
        iteration: Iteration,
        pipeline_dag: nx.DiGraph,
        comp_run: CompRunsAtDB,
    ) -> None:
        tasks = await self._get_pipeline_tasks(project_id, pipeline_dag)
        tasks_inprocess = [t for t in tasks.values() if t.state in PROCESSING_STATES]
        if not tasks_inprocess:
            return

        # get the tasks which state actually changed since last check
        (
            tasks_with_changed_states,
            executing_tasks,
        ) = await self._get_changed_tasks_from_backend(user_id, tasks_inprocess, comp_run)
        # NOTE: typical states a task goes through
        # NOT_STARTED (initial state) -> PUBLISHED (user press run/API call) -> PENDING -> WAITING_FOR_CLUSTER (cluster creation) ->
        # PENDING -> WAITING_FOR_RESOURCES (workers creation or missing) -> PENDING -> STARTED (worker started processing the task) -> SUCCESS/FAILED
        # or ABORTED (user cancelled) or UNKNOWN (lost task - it might be transient, be careful with this one)
        sorted_tasks = await _triage_changed_tasks(tasks_with_changed_states)
        _logger.debug("found the following %s tasks with changed states", sorted_tasks)
        # now process the tasks
        if sorted_tasks.started:
            # NOTE: the dask-scheduler cannot differentiate between tasks that are effectively computing and
            # tasks that are only queued and accepted by a dask-worker. We use dask plugins to report on tasks states
            # states are published to log_event, and we directly publish into RabbitMQ the sidecar and services logs.
            # tasks_started should therefore be mostly empty but for cases where
            # - dask log_event/subscribe_topic mechanism failed, the tasks goes from PENDING -> SUCCESS/FAILED/ABORTED without STARTED
            # - the task finished so fast that the STARTED state was skipped between 2 runs of the dv-2 comp scheduler
            await self._process_started_tasks(
                sorted_tasks.started,
                user_id=user_id,
                project_id=project_id,
                iteration=iteration,
                run_metadata=comp_run.metadata,
                run_id=comp_run.run_id,
            )

        if sorted_tasks.completed or sorted_tasks.potentially_lost:
            await self._process_completed_tasks(
                user_id,
                sorted_tasks.completed + sorted_tasks.potentially_lost,
                iteration,
                comp_run=comp_run,
            )

        if sorted_tasks.waiting:
            await self._process_waiting_tasks(sorted_tasks.waiting, comp_run.run_id)

        if executing_tasks:
            await self._process_executing_tasks(user_id, executing_tasks, comp_run)

    @abstractmethod
    async def _start_tasks(
        self,
        *,
        user_id: UserID,
        project_id: ProjectID,
        scheduled_tasks: dict[NodeID, CompTaskAtDB],
        comp_run: CompRunsAtDB,
        wake_up_callback: Callable[[], None],
    ) -> None:
        """start tasks in the 3rd party backend"""

    @abstractmethod
    async def _get_tasks_status(
        self, user_id: UserID, tasks: list[CompTaskAtDB], comp_run: CompRunsAtDB
    ) -> list[RunningState]:
        """returns tasks status from the 3rd party backend"""

    @abstractmethod
    async def _stop_tasks(self, user_id: UserID, tasks: list[CompTaskAtDB], comp_run: CompRunsAtDB) -> None:
        """stop tasks in the 3rd party backend"""

    @abstractmethod
    async def _process_completed_tasks(
        self,
        user_id: UserID,
        tasks: list[TaskStateTracker],
        iteration: Iteration,
        comp_run: CompRunsAtDB,
    ) -> None:
        """process tasks from the 3rd party backend"""

    @abstractmethod
    async def _process_executing_tasks(
        self,
        user_id: UserID,
        tasks: list[CompTaskAtDB],
        comp_run: CompRunsAtDB,
    ) -> None:
        """process executing tasks from the 3rd party backend"""

    @abstractmethod
    async def _release_resources(self, comp_run: CompRunsAtDB) -> None:
        """release resources used by the scheduler for a given user and project"""

    async def apply(
        self,
        *,
        user_id: UserID,
        project_id: ProjectID,
        iteration: Iteration,
    ) -> None:
        """apply the scheduling of a pipeline for a given user, project and iteration."""
        with log_context(
            _logger,
            level=logging.INFO,
            msg=f"scheduling pipeline {user_id=}:{project_id=}:{iteration=}",
        ):
            dag: nx.DiGraph = nx.DiGraph()

            try:
                comp_run = await CompRunsRepository.instance(self.db_engine).get(user_id, project_id, iteration)
                dag = await self._get_pipeline_dag(project_id)

                # 1. Update our list of tasks with data from backend (state, results)
                await self._update_states_from_comp_backend(user_id, project_id, iteration, dag, comp_run)
                # 1.1. get the updated tasks NOTE: we need to get them again as some states might have changed
                comp_tasks = await self._get_pipeline_tasks(project_id, dag)
                # 2. timeout if waiting for cluster has been there for more than X minutes
                comp_tasks = await self._timeout_if_waiting_for_cluster_too_long(
                    user_id, project_id, comp_run, comp_tasks
                )
                # 3. Any task following a FAILED task shall be ABORTED
                comp_tasks = await self._set_states_following_failed_to_aborted(
                    project_id, dag, comp_tasks, comp_run.run_id
                )
                # 4. do we want to stop the pipeline now?
                if comp_run.cancelled:
                    comp_tasks = await self._schedule_tasks_to_stop(user_id, project_id, comp_tasks, comp_run)
                else:
                    # let's get the tasks to schedule then
                    comp_tasks = await self._schedule_tasks_to_start(
                        user_id=user_id,
                        project_id=project_id,
                        comp_tasks=comp_tasks,
                        dag=dag,
                        comp_run=comp_run,
                        wake_up_callback=_auto_schedule_callback(
                            asyncio.get_running_loop(),
                            self.db_engine,
                            self.rabbitmq_client,
                            user_id=user_id,
                            project_id=project_id,
                            iteration=iteration,
                        ),
                    )

                # 5. send a heartbeat
                await self._send_running_tasks_heartbeat(user_id, project_id, comp_run.run_id, iteration, dag)

                # 6. Update the run result
                pipeline_result = await self._update_run_result_from_tasks(
                    user_id, project_id, iteration, comp_tasks, comp_run.result
                )

                # 7. Are we done scheduling that pipeline?
                if not dag.nodes() or pipeline_result in COMPLETED_STATES:
                    await self._release_resources(comp_run)
                    # there is nothing left, the run is completed, we're done here
                    _logger.info(
                        "pipeline %s scheduling completed with result %s",
                        f"{project_id=}",
                        f"{pipeline_result=}",
                    )
            except PipelineNotFoundError as exc:
                _logger.exception(
                    **create_troubleshooting_log_kwargs(
                        f"pipeline {project_id} is missing from `comp_pipelines` DB table, something is corrupted. Aborting scheduling",
                        error=exc,
                        error_context={
                            "user_id": f"{user_id}",
                            "project_id": f"{project_id}",
                            "iteration": f"{iteration}",
                        },
                        tip="Check that the project still exists",
                    )
                )

                # NOTE: no need to update task states here as pipeline is already broken
                await self._set_run_result(user_id, project_id, iteration, RunningState.FAILED)
            except InvalidPipelineError as exc:
                _logger.exception(
                    **create_troubleshooting_log_kwargs(
                        f"pipeline {project_id} appears to be misconfigured. Aborting scheduling",
                        error=exc,
                        error_context={
                            "user_id": f"{user_id}",
                            "project_id": f"{project_id}",
                            "iteration": f"{iteration}",
                        },
                        tip="Check that the project pipeline is valid and all tasks are present in the DB",
                    ),
                )
                # NOTE: no need to update task states here as pipeline is already broken
                await self._set_run_result(user_id, project_id, iteration, RunningState.FAILED)
            except (
                DaskClientAcquisisitonError,
                ComputationalBackendNotConnectedError,
                ClustersKeeperNotAvailableError,
            ) as exc:
                _logger.exception(
                    **create_troubleshooting_log_kwargs(
                        "Unexpectedly lost connection to the computational backend. Tasks are set back to WAITING_FOR_CLUSTER state until we eventually reconnect",
                        error=exc,
                        error_context={
                            "user_id": f"{user_id}",
                            "project_id": f"{project_id}",
                            "iteration": f"{iteration}",
                        },
                        tip="Check network connection and the status of the computational backend (clusters-keeper, dask-scheduler, dask-workers)",
                    )
                )
                processing_tasks = {
                    k: v
                    for k, v in (await self._get_pipeline_tasks(project_id, dag)).items()
                    if v.state in PROCESSING_STATES
                }
                comp_tasks_repo = CompTasksRepository(self.db_engine)
                await comp_tasks_repo.update_project_tasks_state(
                    project_id,
                    comp_run.run_id,
                    [t.node_id for t in processing_tasks.values()],
                    RunningState.WAITING_FOR_CLUSTER,
                )
                await self._set_run_result(user_id, project_id, iteration, RunningState.WAITING_FOR_CLUSTER)
            finally:
                await self._set_processing_done(user_id, project_id, iteration)

    async def _schedule_tasks_to_stop(
        self,
        user_id: UserID,
        project_id: ProjectID,
        comp_tasks: dict[NodeIDStr, CompTaskAtDB],
        comp_run: CompRunsAtDB,
    ) -> dict[NodeIDStr, CompTaskAtDB]:
        # NOTE: tasks that were not yet started but can be marked as ABORTED straight away,
        # the tasks that are already processing need some time to stop
        # and we need to stop them in the backend
        tasks_instantly_stopeable = [t for t in comp_tasks.values() if t.state in TASK_TO_START_STATES]
        comp_tasks_repo = CompTasksRepository.instance(self.db_engine)
        await comp_tasks_repo.mark_project_published_waiting_for_cluster_tasks_as_aborted(project_id, comp_run.run_id)
        for task in tasks_instantly_stopeable:
            comp_tasks[f"{task.node_id}"].state = RunningState.ABORTED
        # stop any remaining running task, these are already submitted
        if tasks_to_stop := [t for t in comp_tasks.values() if t.state in PROCESSING_STATES]:
            await self._stop_tasks(user_id, tasks_to_stop, comp_run)

        return comp_tasks

    async def _schedule_tasks_to_start(
        self,
        user_id: UserID,
        project_id: ProjectID,
        comp_tasks: dict[NodeIDStr, CompTaskAtDB],
        dag: nx.DiGraph,
        comp_run: CompRunsAtDB,
        wake_up_callback: Callable[[], None],
    ) -> dict[NodeIDStr, CompTaskAtDB]:
        # filter out the successfully completed tasks
        dag.remove_nodes_from({node_id for node_id, t in comp_tasks.items() if t.state == RunningState.SUCCESS})
        dag_in_degree = dag.in_degree()
        assert isinstance(dag_in_degree, InDegreeView)  # nosec
        next_task_node_ids = [node_id for node_id, degree in dag_in_degree if degree == 0]

        # get the tasks to start
        tasks_ready_to_start: dict[NodeID, CompTaskAtDB] = {
            node_id: comp_tasks[f"{node_id}"]
            for node_id in next_task_node_ids
            if comp_tasks[f"{node_id}"].state in TASK_TO_START_STATES
        }

        if not tasks_ready_to_start:
            # nothing to do
            return comp_tasks

        log_error_context = {
            "user_id": f"{user_id}",
            "project_id": f"{project_id}",
            "tasks_ready_to_start": f"{list(tasks_ready_to_start.keys())}",
            "comp_run_use_on_demand_clusters": f"{comp_run.use_on_demand_clusters}",
            "comp_run_run_id": f"{comp_run.run_id}",
        }
        try:
            await self._start_tasks(
                user_id=user_id,
                project_id=project_id,
                scheduled_tasks=tasks_ready_to_start,
                comp_run=comp_run,
                wake_up_callback=wake_up_callback,
            )
        except ComputationalBackendOnDemandNotReadyError as exc:
            _logger.info(
                **create_troubleshooting_log_kwargs(
                    "The on demand computational backend is not ready yet. Tasks are set to WAITING_FOR_CLUSTER state until the cluster is ready!",
                    error=exc,
                    error_context=log_error_context,
                )
            )
            await publish_project_log(
                self.rabbitmq_client,
                user_id,
                project_id,
                log=f"{exc}",
                log_level=logging.INFO,
            )
            await CompTasksRepository.instance(self.db_engine).update_project_tasks_state(
                project_id,
                comp_run.run_id,
                list(tasks_ready_to_start.keys()),
                RunningState.WAITING_FOR_CLUSTER,
            )
            for task in tasks_ready_to_start:
                comp_tasks[f"{task}"].state = RunningState.WAITING_FOR_CLUSTER
        except (
            ComputationalBackendNotConnectedError,
            ComputationalSchedulerChangedError,
            ClustersKeeperNotAvailableError,
        ) as exc:
            _logger.exception(
                **create_troubleshooting_log_kwargs(
                    "Computational backend is not connected. Tasks are set back "
                    "to WAITING_FOR_CLUSTER state until scheduler comes back!",
                    error=exc,
                    error_context=log_error_context,
                )
            )
            await publish_project_log(
                self.rabbitmq_client,
                user_id,
                project_id,
                log=user_message(
                    "An unexpected error occurred during task scheduling. Please contact oSparc support if this issue persists.",
                    _version=1,
                ),
                log_level=logging.ERROR,
            )
            await CompTasksRepository.instance(self.db_engine).update_project_tasks_state(
                project_id,
                comp_run.run_id,
                list(tasks_ready_to_start.keys()),
                RunningState.WAITING_FOR_CLUSTER,
            )
            for task in tasks_ready_to_start:
                comp_tasks[f"{task}"].state = RunningState.WAITING_FOR_CLUSTER

        except Exception as exc:
            _logger.exception(
                **create_troubleshooting_log_kwargs(
                    "Unexpected error happened when scheduling tasks, all tasks to start are set to FAILED and the rest of the pipeline will be ABORTED",
                    error=exc,
                    error_context=log_error_context,
                )
            )
            await CompTasksRepository.instance(self.db_engine).update_project_tasks_state(
                project_id,
                comp_run.run_id,
                list(tasks_ready_to_start.keys()),
                RunningState.FAILED,
                optional_progress=1.0,
                optional_stopped=arrow.utcnow().datetime,
            )
            for task in tasks_ready_to_start:
                comp_tasks[f"{task}"].state = RunningState.FAILED
            raise

        return comp_tasks

    async def _timeout_if_waiting_for_cluster_too_long(
        self,
        user_id: UserID,
        project_id: ProjectID,
        comp_run: CompRunsAtDB,
        comp_tasks: dict[NodeIDStr, CompTaskAtDB],
    ) -> dict[NodeIDStr, CompTaskAtDB]:
        if comp_run.result is not RunningState.WAITING_FOR_CLUSTER:
            return comp_tasks

        tasks_waiting_for_cluster = [t for t in comp_tasks.values() if t.state is RunningState.WAITING_FOR_CLUSTER]
        if not tasks_waiting_for_cluster:
            return comp_tasks

        # get latest modified task
        latest_modified_of_all_tasks = max(tasks_waiting_for_cluster, key=lambda task: task.modified).modified

        if (
            arrow.utcnow().datetime - latest_modified_of_all_tasks
        ) > self.settings.COMPUTATIONAL_BACKEND_MAX_WAITING_FOR_CLUSTER_TIMEOUT:
            await CompTasksRepository.instance(self.db_engine).update_project_tasks_state(
                project_id,
                comp_run.run_id,
                [task.node_id for task in tasks_waiting_for_cluster],
                RunningState.FAILED,
                optional_progress=1.0,
                optional_stopped=arrow.utcnow().datetime,
            )
            for task in tasks_waiting_for_cluster:
                task.state = RunningState.FAILED
            msg = user_message(
                "The system has timed out while waiting for computational resources. Please try running your project again or contact oSparc support if this issue persists.",
                _version=1,
            )
            _logger.error(msg)
            await publish_project_log(
                self.rabbitmq_client,
                user_id,
                project_id,
                log=msg,
                log_level=logging.ERROR,
            )
        return comp_tasks
