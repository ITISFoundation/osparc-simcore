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
from dataclasses import dataclass, field
from typing import Final

import arrow
import networkx as nx
from aiopg.sa.engine import Engine
from models_library.clusters import ClusterID
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID, NodeIDStr
from models_library.projects_state import RunningState
from models_library.services import ServiceKey, ServiceType, ServiceVersion
from models_library.users import UserID
from pydantic import PositiveInt
from servicelib.common_headers import UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE
from servicelib.rabbitmq import RabbitMQClient, RabbitMQRPCClient
from servicelib.utils import logged_gather

from ...constants import UNDEFINED_STR_METADATA
from ...core.errors import (
    ClustersKeeperNotAvailableError,
    ComputationalBackendNotConnectedError,
    ComputationalBackendOnDemandNotReadyError,
    ComputationalSchedulerChangedError,
    DaskClientAcquisisitonError,
    InvalidPipelineError,
    PipelineNotFoundError,
    SchedulerError,
    TaskSchedulingError,
)
from ...core.settings import ComputationalBackendSettings
from ...models.comp_pipelines import CompPipelineAtDB
from ...models.comp_runs import CompRunsAtDB, RunMetadataDict
from ...models.comp_tasks import CompTaskAtDB
from ...utils.comp_scheduler import (
    COMPLETED_STATES,
    PROCESSING_STATES,
    RUNNING_STATES,
    TASK_TO_START_STATES,
    WAITING_FOR_START_STATES,
    Iteration,
    create_service_resources_from_task,
    get_resource_tracking_run_id,
)
from ...utils.computations import get_pipeline_state_from_task_states
from ...utils.rabbitmq import (
    publish_project_log,
    publish_service_resource_tracking_heartbeat,
    publish_service_resource_tracking_started,
    publish_service_started_metrics,
)
from ..db.repositories.comp_pipelines import CompPipelinesRepository
from ..db.repositories.comp_runs import CompRunsRepository
from ..db.repositories.comp_tasks import CompTasksRepository

_logger = logging.getLogger(__name__)


_Previous = CompTaskAtDB
_Current = CompTaskAtDB
_MAX_WAITING_FOR_CLUSTER_TIMEOUT_IN_MIN: Final[int] = 10


@dataclass(frozen=True, slots=True)
class SortedTasks:
    started: list[CompTaskAtDB]
    completed: list[CompTaskAtDB]
    waiting: list[CompTaskAtDB]
    potentially_lost: list[CompTaskAtDB]


async def _triage_changed_tasks(
    changed_tasks: list[tuple[_Previous, _Current]]
) -> SortedTasks:
    started_tasks = [
        current
        for previous, current in changed_tasks
        if current.state in RUNNING_STATES
        or (
            previous.state in WAITING_FOR_START_STATES
            and current.state in COMPLETED_STATES
        )
    ]

    # NOTE: some tasks can be both started and completed since we might have the time they were running
    completed_tasks = [
        current for _, current in changed_tasks if current.state in COMPLETED_STATES
    ]

    waiting_for_resources_tasks = [
        current
        for previous, current in changed_tasks
        if current.state in WAITING_FOR_START_STATES
    ]

    lost_or_momentarily_lost_tasks = [
        current for _, current in changed_tasks if current.state is RunningState.UNKNOWN
    ]
    if lost_or_momentarily_lost_tasks:
        _logger.warning(
            "%s are currently in unknown state. TIP: If they are running in an external cluster and it is not yet ready, that might explain it. But inform @sanderegg nevertheless!",
            [t.node_id for t in lost_or_momentarily_lost_tasks],
        )

    return SortedTasks(
        started_tasks,
        completed_tasks,
        waiting_for_resources_tasks,
        lost_or_momentarily_lost_tasks,
    )


@dataclass(kw_only=True)
class ScheduledPipelineParams:
    cluster_id: ClusterID
    run_metadata: RunMetadataDict
    mark_for_cancellation: bool = False
    use_on_demand_clusters: bool


@dataclass
class BaseCompScheduler(ABC):
    scheduled_pipelines: dict[
        tuple[UserID, ProjectID, Iteration], ScheduledPipelineParams
    ]
    db_engine: Engine
    wake_up_event: asyncio.Event = field(default_factory=asyncio.Event, init=False)
    rabbitmq_client: RabbitMQClient
    rabbitmq_rpc_client: RabbitMQRPCClient
    settings: ComputationalBackendSettings
    service_runtime_heartbeat_interval: datetime.timedelta

    async def run_new_pipeline(
        self,
        user_id: UserID,
        project_id: ProjectID,
        cluster_id: ClusterID,
        run_metadata: RunMetadataDict,
        *,
        use_on_demand_clusters: bool,
    ) -> None:
        """Sets a new pipeline to be scheduled on the computational resources.
        Passing cluster_id=0 will use the default cluster. Passing an existing ID will instruct
        the scheduler to run the tasks on the defined cluster"""
        # ensure the pipeline exists and is populated with something
        dag = await self._get_pipeline_dag(project_id)
        if not dag:
            _logger.warning(
                "project %s has no computational dag defined. not scheduled for a run.",
                f"{project_id=}",
            )
            return

        runs_repo = CompRunsRepository.instance(self.db_engine)
        new_run: CompRunsAtDB = await runs_repo.create(
            user_id=user_id,
            project_id=project_id,
            cluster_id=cluster_id,
            metadata=run_metadata,
            use_on_demand_clusters=use_on_demand_clusters,
        )
        self.scheduled_pipelines[
            (user_id, project_id, new_run.iteration)
        ] = ScheduledPipelineParams(
            cluster_id=cluster_id,
            run_metadata=new_run.metadata,
            use_on_demand_clusters=use_on_demand_clusters,
        )
        await publish_project_log(
            self.rabbitmq_client,
            user_id,
            project_id,
            log=f"Project pipeline scheduled using {'on-demand clusters' if use_on_demand_clusters else 'pre-defined clusters'}, starting soon...",
            log_level=logging.INFO,
        )
        # ensure the scheduler starts right away
        self._wake_up_scheduler_now()

    async def stop_pipeline(
        self, user_id: UserID, project_id: ProjectID, iteration: int | None = None
    ) -> None:
        if iteration is None:
            # if no iteration given find the latest one in the list
            possible_iterations = {
                it
                for u_id, p_id, it in self.scheduled_pipelines
                if u_id == user_id and p_id == project_id
            }
            if not possible_iterations:
                msg = f"There are no pipeline scheduled for {user_id}:{project_id}"
                raise SchedulerError(msg)
            current_max_iteration = max(possible_iterations)
            selected_iteration = current_max_iteration
        else:
            selected_iteration = iteration

        # mark the scheduled pipeline for stopping
        self.scheduled_pipelines[
            (user_id, project_id, selected_iteration)
        ].mark_for_cancellation = True
        # ensure the scheduler starts right away
        self._wake_up_scheduler_now()

    async def schedule_all_pipelines(self) -> None:
        self.wake_up_event.clear()
        # if one of the task throws, the other are NOT cancelled which is what we want
        await logged_gather(
            *(
                self._schedule_pipeline(
                    user_id=user_id,
                    project_id=project_id,
                    iteration=iteration,
                    pipeline_params=pipeline_params,
                )
                for (
                    user_id,
                    project_id,
                    iteration,
                ), pipeline_params in self.scheduled_pipelines.items()
            ),
            log=_logger,
            max_concurrency=40,
        )

    async def _get_pipeline_dag(self, project_id: ProjectID) -> nx.DiGraph:
        comp_pipeline_repo = CompPipelinesRepository.instance(self.db_engine)
        pipeline_at_db: CompPipelineAtDB = await comp_pipeline_repo.get_pipeline(
            project_id
        )
        dag = pipeline_at_db.get_graph()
        _logger.debug("%s: current %s", f"{project_id=}", f"{dag=}")
        return dag

    async def _get_pipeline_tasks(
        self, project_id: ProjectID, pipeline_dag: nx.DiGraph
    ) -> dict[NodeIDStr, CompTaskAtDB]:
        comp_tasks_repo = CompTasksRepository.instance(self.db_engine)
        pipeline_comp_tasks: dict[NodeIDStr, CompTaskAtDB] = {
            NodeIDStr(f"{t.node_id}"): t
            for t in await comp_tasks_repo.list_computational_tasks(project_id)
            if (f"{t.node_id}" in list(pipeline_dag.nodes()))
        }
        if len(pipeline_comp_tasks) != len(pipeline_dag.nodes()):
            msg = (
                f"{project_id}The tasks defined for {project_id} do not contain all"
                f" the tasks defined in the pipeline [{list(pipeline_dag.nodes)}]! Please check."
            )
            raise InvalidPipelineError(msg)
        return pipeline_comp_tasks

    async def _update_run_result_from_tasks(
        self,
        user_id: UserID,
        project_id: ProjectID,
        iteration: PositiveInt,
        pipeline_tasks: dict[NodeIDStr, CompTaskAtDB],
    ) -> RunningState:
        pipeline_state_from_tasks: RunningState = get_pipeline_state_from_task_states(
            list(pipeline_tasks.values()),
        )
        _logger.debug(
            "pipeline %s is currently in %s",
            f"{user_id=}_{project_id=}_{iteration=}",
            f"{pipeline_state_from_tasks}",
        )
        await self._set_run_result(
            user_id, project_id, iteration, pipeline_state_from_tasks
        )
        return pipeline_state_from_tasks

    async def _set_run_result(
        self,
        user_id: UserID,
        project_id: ProjectID,
        iteration: PositiveInt,
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

    async def _set_states_following_failed_to_aborted(
        self, project_id: ProjectID, dag: nx.DiGraph
    ) -> dict[NodeIDStr, CompTaskAtDB]:
        tasks: dict[NodeIDStr, CompTaskAtDB] = await self._get_pipeline_tasks(
            project_id, dag
        )
        tasks_to_set_aborted: set[NodeIDStr] = set()
        for task in tasks.values():
            if task.state == RunningState.FAILED:
                tasks_to_set_aborted.update(nx.bfs_tree(dag, f"{task.node_id}"))
                tasks_to_set_aborted.remove(NodeIDStr(f"{task.node_id}"))
        for task in tasks_to_set_aborted:
            tasks[NodeIDStr(f"{task}")].state = RunningState.ABORTED
        if tasks_to_set_aborted:
            # update the current states back in DB
            comp_tasks_repo = CompTasksRepository.instance(self.db_engine)
            await comp_tasks_repo.update_project_tasks_state(
                project_id,
                [NodeID(n) for n in tasks_to_set_aborted],
                RunningState.ABORTED,
                optional_progress=1.0,
                optional_stopped=arrow.utcnow().datetime,
            )
        return tasks

    async def _send_running_tasks_heartbeat(
        self,
        user_id: UserID,
        project_id: ProjectID,
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
                    (utc_now - task.start.replace(tzinfo=datetime.timezone.utc))
                    > self.service_runtime_heartbeat_interval
                )
            return bool(
                (utc_now - task.last_heartbeat)
                > self.service_runtime_heartbeat_interval
            )

        tasks: dict[NodeIDStr, CompTaskAtDB] = await self._get_pipeline_tasks(
            project_id, dag
        )
        if running_tasks := [t for t in tasks.values() if _need_heartbeat(t)]:
            await asyncio.gather(
                *(
                    publish_service_resource_tracking_heartbeat(
                        self.rabbitmq_client,
                        get_resource_tracking_run_id(
                            user_id, t.project_id, t.node_id, iteration
                        ),
                    )
                    for t in running_tasks
                )
            )
            comp_tasks_repo = CompTasksRepository(self.db_engine)
            await asyncio.gather(
                *(
                    comp_tasks_repo.update_project_task_last_heartbeat(
                        t.project_id, t.node_id, utc_now
                    )
                    for t in running_tasks
                )
            )

    async def _get_changed_tasks_from_backend(
        self,
        user_id: UserID,
        processing_tasks: list[CompTaskAtDB],
        pipeline_params: ScheduledPipelineParams,
    ) -> list[tuple[_Previous, _Current]]:
        tasks_backend_status = await self._get_tasks_status(
            user_id, processing_tasks, pipeline_params
        )

        return [
            (
                task,
                task.copy(update={"state": backend_state}),
            )
            for task, backend_state in zip(
                processing_tasks, tasks_backend_status, strict=True
            )
            if task.state is not backend_state
        ]

    async def _process_started_tasks(
        self,
        tasks: list[CompTaskAtDB],
        *,
        user_id: UserID,
        iteration: Iteration,
        run_metadata: RunMetadataDict,
    ) -> None:
        utc_now = arrow.utcnow().datetime

        # resource tracking
        await asyncio.gather(
            *(
                publish_service_resource_tracking_started(
                    self.rabbitmq_client,
                    service_run_id=get_resource_tracking_run_id(
                        user_id, t.project_id, t.node_id, iteration
                    ),
                    wallet_id=run_metadata.get("wallet_id"),
                    wallet_name=run_metadata.get("wallet_name"),
                    pricing_plan_id=(
                        t.pricing_info.get("pricing_plan_id")
                        if t.pricing_info
                        else None
                    ),
                    pricing_unit_id=(
                        t.pricing_info.get("pricing_unit_id")
                        if t.pricing_info
                        else None
                    ),
                    pricing_unit_cost_id=(
                        t.pricing_info.get("pricing_unit_cost_id")
                        if t.pricing_info
                        else None
                    ),
                    product_name=run_metadata.get(
                        "product_name", UNDEFINED_STR_METADATA
                    ),
                    simcore_user_agent=run_metadata.get(
                        "simcore_user_agent", UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE
                    ),
                    user_id=user_id,
                    user_email=run_metadata.get("user_email", UNDEFINED_STR_METADATA),
                    project_id=t.project_id,
                    project_name=run_metadata.get("project_metadata", {}).get(  # type: ignore[arg-type]
                        "project_name", UNDEFINED_STR_METADATA
                    ),
                    node_id=t.node_id,
                    node_name=run_metadata.get("node_id_names_map", {}).get(
                        t.node_id, UNDEFINED_STR_METADATA
                    ),
                    parent_project_id=run_metadata.get("project_metadata", {}).get(
                        "parent_project_id"
                    ),
                    parent_node_id=run_metadata.get("project_metadata", {}).get(
                        "parent_node_id"
                    ),
                    root_parent_project_id=run_metadata.get("project_metadata", {}).get(
                        "root_parent_project_id"
                    ),
                    root_parent_project_name=run_metadata.get(
                        "project_metadata", {}
                    ).get("root_parent_project_name"),
                    root_parent_node_id=run_metadata.get("project_metadata", {}).get(
                        "root_parent_node_id"
                    ),
                    service_key=ServiceKey(t.image.name),
                    service_version=ServiceVersion(t.image.tag),
                    service_type=ServiceType.COMPUTATIONAL,
                    service_resources=create_service_resources_from_task(t),
                    service_additional_metadata={},
                )
                for t in tasks
            )
        )
        # instrumentation
        await asyncio.gather(
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
            )
        )

        # update DB
        comp_tasks_repo = CompTasksRepository(self.db_engine)
        await asyncio.gather(
            *(
                comp_tasks_repo.update_project_tasks_state(
                    t.project_id,
                    [t.node_id],
                    t.state,
                    optional_started=utc_now,
                    optional_progress=t.progress,
                )
                for t in tasks
            )
        )

    async def _process_waiting_tasks(self, tasks: list[CompTaskAtDB]) -> None:
        comp_tasks_repo = CompTasksRepository(self.db_engine)
        await asyncio.gather(
            *(
                comp_tasks_repo.update_project_tasks_state(
                    t.project_id,
                    [t.node_id],
                    t.state,
                )
                for t in tasks
            )
        )

    async def _update_states_from_comp_backend(
        self,
        user_id: UserID,
        project_id: ProjectID,
        iteration: Iteration,
        pipeline_dag: nx.DiGraph,
        pipeline_params: ScheduledPipelineParams,
    ) -> None:
        tasks = await self._get_pipeline_tasks(project_id, pipeline_dag)
        tasks_inprocess = [t for t in tasks.values() if t.state in PROCESSING_STATES]
        if not tasks_inprocess:
            return

        # get the tasks which state actually changed since last check
        tasks_with_changed_states = await self._get_changed_tasks_from_backend(
            user_id, tasks_inprocess, pipeline_params
        )
        # NOTE: typical states a task goes through
        # NOT_STARTED (initial state) -> PUBLISHED (user press run/API call) -> PENDING -> WAITING_FOR_CLUSTER (cluster creation) ->
        # PENDING -> WAITING_FOR_RESOURCES (workers creation or missing) -> PENDING -> STARTED (worker started processing the task) -> SUCCESS/FAILED
        # or ABORTED (user cancelled) or UNKNOWN (lost task - it might be transient, be careful with this one)
        sorted_tasks = await _triage_changed_tasks(tasks_with_changed_states)

        # now process the tasks
        if sorted_tasks.started:
            # NOTE: the dask-scheduler cannot differentiate between tasks that are effectively computing and
            # tasks that are only queued and accepted by a dask-worker.
            # tasks_started should therefore be mostly empty but for cases where
            # - dask Pub/Sub mechanism failed, the tasks goes from PENDING -> SUCCESS/FAILED/ABORTED without STARTED
            # - the task finished so fast that the STARTED state was skipped between 2 runs of the dv-2 comp scheduler
            await self._process_started_tasks(
                sorted_tasks.started,
                user_id=user_id,
                iteration=iteration,
                run_metadata=pipeline_params.run_metadata,
            )

        if sorted_tasks.completed or sorted_tasks.potentially_lost:
            await self._process_completed_tasks(
                user_id,
                sorted_tasks.completed + sorted_tasks.potentially_lost,
                iteration,
                pipeline_params=pipeline_params,
            )

        if sorted_tasks.waiting:
            await self._process_waiting_tasks(sorted_tasks.waiting)

    @abstractmethod
    async def _start_tasks(
        self,
        *,
        user_id: UserID,
        project_id: ProjectID,
        scheduled_tasks: dict[NodeID, CompTaskAtDB],
        pipeline_params: ScheduledPipelineParams,
    ) -> None:
        ...

    @abstractmethod
    async def _get_tasks_status(
        self,
        user_id: UserID,
        tasks: list[CompTaskAtDB],
        pipeline_params: ScheduledPipelineParams,
    ) -> list[RunningState]:
        ...

    @abstractmethod
    async def _stop_tasks(
        self,
        user_id: UserID,
        tasks: list[CompTaskAtDB],
        pipeline_params: ScheduledPipelineParams,
    ) -> None:
        ...

    @abstractmethod
    async def _process_completed_tasks(
        self,
        user_id: UserID,
        tasks: list[CompTaskAtDB],
        iteration: Iteration,
        pipeline_params: ScheduledPipelineParams,
    ) -> None:
        ...

    async def _schedule_pipeline(
        self,
        *,
        user_id: UserID,
        project_id: ProjectID,
        iteration: PositiveInt,
        pipeline_params: ScheduledPipelineParams,
    ) -> None:
        _logger.debug(
            "checking run of project [%s:%s] for user [%s]",
            f"{project_id=}",
            f"{iteration=}",
            f"{user_id=}",
        )
        dag: nx.DiGraph = nx.DiGraph()
        try:
            dag = await self._get_pipeline_dag(project_id)
            # 1. Update our list of tasks with data from backend (state, results)
            await self._update_states_from_comp_backend(
                user_id, project_id, iteration, dag, pipeline_params=pipeline_params
            )
            # 2. Any task following a FAILED task shall be ABORTED
            comp_tasks = await self._set_states_following_failed_to_aborted(
                project_id, dag
            )
            # 3. do we want to stop the pipeline now?
            if pipeline_params.mark_for_cancellation:
                await self._schedule_tasks_to_stop(
                    user_id, project_id, comp_tasks, pipeline_params
                )
            else:
                # let's get the tasks to schedule then
                comp_tasks = await self._schedule_tasks_to_start(
                    user_id=user_id,
                    project_id=project_id,
                    comp_tasks=comp_tasks,
                    dag=dag,
                    pipeline_params=pipeline_params,
                )
            # 4. timeout if waiting for cluster has been there for more than X minutes
            comp_tasks = await self._timeout_if_waiting_for_cluster_too_long(
                user_id, project_id, comp_tasks
            )
            # 5. send a heartbeat
            await self._send_running_tasks_heartbeat(
                user_id, project_id, iteration, dag
            )

            # 6. Update the run result
            pipeline_result = await self._update_run_result_from_tasks(
                user_id, project_id, iteration, comp_tasks
            )

            # 7. Are we done scheduling that pipeline?
            if not dag.nodes() or pipeline_result in COMPLETED_STATES:
                # there is nothing left, the run is completed, we're done here
                self.scheduled_pipelines.pop((user_id, project_id, iteration), None)
                _logger.info(
                    "pipeline %s scheduling completed with result %s",
                    f"{project_id=}",
                    f"{pipeline_result=}",
                )
        except PipelineNotFoundError:
            _logger.warning(
                "pipeline %s does not exist in comp_pipeline table, it will be removed from scheduler",
                f"{project_id=}",
            )
            await self._set_run_result(
                user_id, project_id, iteration, RunningState.ABORTED
            )
            self.scheduled_pipelines.pop((user_id, project_id, iteration), None)
        except InvalidPipelineError as exc:
            _logger.warning(
                "pipeline %s appears to be misconfigured, it will be removed from scheduler. Please check pipeline:\n%s",
                f"{project_id=}",
                exc,
            )
            await self._set_run_result(
                user_id, project_id, iteration, RunningState.ABORTED
            )
            self.scheduled_pipelines.pop((user_id, project_id, iteration), None)
        except (DaskClientAcquisisitonError, ClustersKeeperNotAvailableError):
            _logger.exception(
                "Unexpected error while connecting with computational backend, aborting pipeline"
            )
            tasks: dict[NodeIDStr, CompTaskAtDB] = await self._get_pipeline_tasks(
                project_id, dag
            )
            comp_tasks_repo = CompTasksRepository(self.db_engine)
            await comp_tasks_repo.update_project_tasks_state(
                project_id,
                [t.node_id for t in tasks.values()],
                RunningState.FAILED,
            )
            await self._set_run_result(
                user_id, project_id, iteration, RunningState.FAILED
            )
            self.scheduled_pipelines.pop((user_id, project_id, iteration), None)
        except ComputationalBackendNotConnectedError:
            _logger.exception("Computational backend is not connected!")

    async def _schedule_tasks_to_stop(
        self,
        user_id: UserID,
        project_id: ProjectID,
        comp_tasks: dict[NodeIDStr, CompTaskAtDB],
        pipeline_params: ScheduledPipelineParams,
    ) -> None:
        # get any running task and stop them
        comp_tasks_repo = CompTasksRepository.instance(self.db_engine)
        await comp_tasks_repo.mark_project_published_waiting_for_cluster_tasks_as_aborted(
            project_id
        )
        # stop any remaining running task, these are already submitted
        tasks_to_stop = [t for t in comp_tasks.values() if t.state in PROCESSING_STATES]
        await self._stop_tasks(user_id, tasks_to_stop, pipeline_params)

    async def _schedule_tasks_to_start(  # noqa: C901
        self,
        user_id: UserID,
        project_id: ProjectID,
        comp_tasks: dict[NodeIDStr, CompTaskAtDB],
        dag: nx.DiGraph,
        pipeline_params: ScheduledPipelineParams,
    ) -> dict[NodeIDStr, CompTaskAtDB]:
        # filter out the successfully completed tasks
        dag.remove_nodes_from(
            {
                node_id
                for node_id, t in comp_tasks.items()
                if t.state == RunningState.SUCCESS
            }
        )
        next_task_node_ids = [
            node_id for node_id, degree in dag.in_degree() if degree == 0
        ]

        # get the tasks to start
        tasks_ready_to_start: dict[NodeID, CompTaskAtDB] = {
            node_id: comp_tasks[NodeIDStr(f"{node_id}")]
            for node_id in next_task_node_ids
            if comp_tasks[NodeIDStr(f"{node_id}")].state in TASK_TO_START_STATES
        }

        if not tasks_ready_to_start:
            # nothing to do
            return comp_tasks

        try:
            await self._start_tasks(
                user_id=user_id,
                project_id=project_id,
                scheduled_tasks=tasks_ready_to_start,
                pipeline_params=pipeline_params,
            )
        except (
            ComputationalBackendNotConnectedError,
            ComputationalSchedulerChangedError,
        ):
            _logger.exception(
                "Issue with computational backend. Tasks are set back "
                "to WAITING_FOR_CLUSTER state until scheduler comes back!",
            )
            await CompTasksRepository.instance(
                self.db_engine
            ).update_project_tasks_state(
                project_id,
                list(tasks_ready_to_start.keys()),
                RunningState.WAITING_FOR_CLUSTER,
            )
            for task in tasks_ready_to_start:
                comp_tasks[
                    NodeIDStr(f"{task}")
                ].state = RunningState.WAITING_FOR_CLUSTER

        except ComputationalBackendOnDemandNotReadyError as exc:
            _logger.info(
                "The on demand computational backend is not ready yet: %s", exc
            )
            await publish_project_log(
                self.rabbitmq_client,
                user_id,
                project_id,
                log=f"{exc}",
                log_level=logging.INFO,
            )

            await CompTasksRepository.instance(
                self.db_engine
            ).update_project_tasks_state(
                project_id,
                list(tasks_ready_to_start.keys()),
                RunningState.WAITING_FOR_CLUSTER,
            )
            for task in tasks_ready_to_start:
                comp_tasks[
                    NodeIDStr(f"{task}")
                ].state = RunningState.WAITING_FOR_CLUSTER
        except ClustersKeeperNotAvailableError:
            _logger.exception("Unexpected error while starting tasks:")
            await publish_project_log(
                self.rabbitmq_client,
                user_id,
                project_id,
                log="Unexpected error while scheduling computational tasks! TIP: contact osparc support.",
                log_level=logging.ERROR,
            )

            await CompTasksRepository.instance(
                self.db_engine
            ).update_project_tasks_state(
                project_id,
                list(tasks_ready_to_start.keys()),
                RunningState.FAILED,
                optional_progress=1.0,
                optional_stopped=arrow.utcnow().datetime,
            )
            for task in tasks_ready_to_start:
                comp_tasks[NodeIDStr(f"{task}")].state = RunningState.FAILED
            raise
        except TaskSchedulingError as exc:
            _logger.exception(
                "Project '%s''s task '%s' could not be scheduled",
                exc.project_id,
                exc.node_id,
            )
            await CompTasksRepository.instance(
                self.db_engine
            ).update_project_tasks_state(
                project_id,
                [exc.node_id],
                RunningState.FAILED,
                exc.get_errors(),
                optional_progress=1.0,
                optional_stopped=arrow.utcnow().datetime,
            )
            comp_tasks[NodeIDStr(f"{exc.node_id}")].state = RunningState.FAILED
        except Exception:
            _logger.exception(
                "Unexpected error for %s with %s on %s happened when scheduling %s:",
                f"{user_id=}",
                f"{project_id=}",
                f"{pipeline_params.cluster_id=}",
                f"{tasks_ready_to_start.keys()=}",
            )
            await CompTasksRepository.instance(
                self.db_engine
            ).update_project_tasks_state(
                project_id,
                list(tasks_ready_to_start.keys()),
                RunningState.FAILED,
                optional_progress=1.0,
                optional_stopped=arrow.utcnow().datetime,
            )
            for task in tasks_ready_to_start:
                comp_tasks[NodeIDStr(f"{task}")].state = RunningState.FAILED
            raise

        return comp_tasks

    async def _timeout_if_waiting_for_cluster_too_long(
        self,
        user_id: UserID,
        project_id: ProjectID,
        comp_tasks: dict[NodeIDStr, CompTaskAtDB],
    ) -> dict[NodeIDStr, CompTaskAtDB]:
        if all(
            c.state is RunningState.WAITING_FOR_CLUSTER for c in comp_tasks.values()
        ):
            # get latest modified task
            latest_modified_of_all_tasks = max(
                comp_tasks.values(), key=lambda task: task.modified
            ).modified

            if (
                arrow.utcnow().datetime - latest_modified_of_all_tasks
            ) > datetime.timedelta(minutes=_MAX_WAITING_FOR_CLUSTER_TIMEOUT_IN_MIN):
                await CompTasksRepository.instance(
                    self.db_engine
                ).update_project_tasks_state(
                    project_id,
                    [NodeID(idstr) for idstr in comp_tasks],
                    RunningState.FAILED,
                    optional_progress=1.0,
                    optional_stopped=arrow.utcnow().datetime,
                )
                for task in comp_tasks.values():
                    task.state = RunningState.FAILED
                msg = "Timed-out waiting for computational cluster! Please try again and/or contact Osparc support."
                _logger.error(msg)
                await publish_project_log(
                    self.rabbitmq_client,
                    user_id,
                    project_id,
                    log=msg,
                    log_level=logging.ERROR,
                )
        return comp_tasks

    def _wake_up_scheduler_now(self) -> None:
        self.wake_up_event.set()
