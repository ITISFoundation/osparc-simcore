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
import logging
import traceback
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

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
from servicelib.rabbitmq import RabbitMQClient
from servicelib.utils import logged_gather

from ...core.errors import (
    ComputationalBackendNotConnectedError,
    ComputationalSchedulerChangedError,
    InvalidPipelineError,
    PipelineNotFoundError,
    SchedulerError,
    TaskSchedulingError,
)
from ...models.comp_pipelines import CompPipelineAtDB
from ...models.comp_runs import CompRunsAtDB, MetadataDict
from ...models.comp_tasks import CompTaskAtDB, Image
from ...utils.comp_scheduler import (
    COMPLETED_STATES,
    PROCESSING_STATES,
    RUNNING_STATES,
    WAITING_FOR_START_STATES,
    Iteration,
    create_service_resources_from_task,
    get_resource_tracking_run_id,
)
from ...utils.computations import get_pipeline_state_from_task_states
from ...utils.rabbitmq import (
    publish_service_resource_tracking_heartbeat,
    publish_service_resource_tracking_started,
    publish_service_started_metrics,
)
from ..db.repositories.comp_pipelines import CompPipelinesRepository
from ..db.repositories.comp_runs import CompRunsRepository
from ..db.repositories.comp_tasks import CompTasksRepository

_logger = logging.getLogger(__name__)


@dataclass(kw_only=True)
class ScheduledPipelineParams:
    cluster_id: ClusterID
    run_metadata: MetadataDict
    mark_for_cancellation: bool = False


_Previous = CompTaskAtDB
_Current = CompTaskAtDB


@dataclass
class BaseCompScheduler(ABC):
    scheduled_pipelines: dict[
        tuple[UserID, ProjectID, Iteration], ScheduledPipelineParams
    ]
    db_engine: Engine
    wake_up_event: asyncio.Event = field(default_factory=asyncio.Event, init=False)
    rabbitmq_client: RabbitMQClient

    async def run_new_pipeline(
        self,
        user_id: UserID,
        project_id: ProjectID,
        cluster_id: ClusterID,
        run_metadata: MetadataDict,
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
        )
        self.scheduled_pipelines[
            (user_id, project_id, new_run.iteration)
        ] = ScheduledPipelineParams(
            cluster_id=cluster_id, run_metadata=new_run.metadata
        )
        # ensure the scheduler starts right away
        self._wake_up_scheduler_now()

    async def stop_pipeline(
        self, user_id: UserID, project_id: ProjectID, iteration: int | None = None
    ) -> None:
        if not iteration:
            # if no iteration given find the latest one in the list
            possible_iterations = {
                it
                for u_id, p_id, it in self.scheduled_pipelines
                if u_id == user_id and p_id == project_id
            }
            if not possible_iterations:
                msg = f"There are no pipeline scheduled for {user_id}:{project_id}"
                raise SchedulerError(msg)
            iteration = max(possible_iterations)

        # mark the scheduled pipeline for stopping
        self.scheduled_pipelines[
            (user_id, project_id, iteration)
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
                    cluster_id=pipeline_params.cluster_id,
                    iteration=iteration,
                    marked_for_stopping=pipeline_params.mark_for_cancellation,
                    run_metadata=pipeline_params.run_metadata,
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
    ) -> dict[str, CompTaskAtDB]:
        comp_tasks_repo = CompTasksRepository.instance(self.db_engine)
        pipeline_comp_tasks: dict[str, CompTaskAtDB] = {
            f"{t.node_id}": t
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
        pipeline_tasks: dict[str, CompTaskAtDB],
    ) -> RunningState:
        pipeline_state_from_tasks: RunningState = get_pipeline_state_from_task_states(
            list(pipeline_tasks.values()),
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
    ) -> dict[str, CompTaskAtDB]:
        tasks: dict[str, CompTaskAtDB] = await self._get_pipeline_tasks(project_id, dag)
        tasks_to_set_aborted: set[NodeIDStr] = set()
        for task in tasks.values():
            if task.state == RunningState.FAILED:
                tasks_to_set_aborted.update(nx.bfs_tree(dag, f"{task.node_id}"))
                tasks_to_set_aborted.remove(NodeIDStr(f"{task.node_id}"))
        for task in tasks_to_set_aborted:
            tasks[f"{task}"].state = RunningState.ABORTED
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

    async def _get_changed_tasks_from_backend(
        self,
        user_id: UserID,
        cluster_id: ClusterID,
        processing_tasks: list[CompTaskAtDB],
    ) -> list[tuple[_Previous, _Current]]:
        tasks_backend_status = await self._get_tasks_status(
            user_id, cluster_id, processing_tasks
        )
        return [
            (
                task,
                task.copy(update={"state": backend_state}),
            )
            for task, backend_state in zip(
                processing_tasks, tasks_backend_status, strict=False
            )
            if task.state is not backend_state
        ]

    async def _process_started_tasks(
        self,
        tasks: list[CompTaskAtDB],
        *,
        user_id: UserID,
        iteration: Iteration,
        run_metadata: MetadataDict,
    ) -> None:
        # resource tracking
        await asyncio.gather(
            *(
                publish_service_resource_tracking_started(
                    self.rabbitmq_client,
                    service_run_id=get_resource_tracking_run_id(
                        user_id, t.project_id, iteration
                    ),
                    wallet_id=run_metadata["wallet_id"],
                    wallet_name=run_metadata["wallet_name"],
                    product_name=run_metadata["product_name"],
                    simcore_user_agent=run_metadata["simcore_user_agent"],
                    user_id=user_id,
                    user_email=run_metadata["user_email"],
                    project_id=t.project_id,
                    project_name=run_metadata["project_name"],
                    node_id=t.node_id,
                    node_name=run_metadata["node_id_names_map"].get(
                        t.node_id, "undefined"
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
                    simcore_user_agent=run_metadata["simcore_user_agent"],
                    task=t,
                )
                for t in tasks
            )
        )

    async def _process_incomplete_tasks(self, tasks: list[CompTaskAtDB]) -> None:
        comp_tasks_repo = CompTasksRepository(self.db_engine)
        await asyncio.gather(
            *(
                comp_tasks_repo.update_project_tasks_state(
                    t.project_id,
                    [t.node_id],
                    t.state,
                    optional_started=arrow.utcnow().datetime
                    if t.state is RunningState.STARTED
                    else None,
                )
                for t in tasks
            )
        )

    async def _update_states_from_comp_backend(
        self,
        user_id: UserID,
        cluster_id: ClusterID,
        project_id: ProjectID,
        iteration: Iteration,
        pipeline_dag: nx.DiGraph,
        run_metadata: MetadataDict,
    ) -> None:
        all_tasks = await self._get_pipeline_tasks(project_id, pipeline_dag)
        if processing_tasks := [
            t for t in all_tasks.values() if t.state in PROCESSING_STATES
        ]:
            changed_tasks = await self._get_changed_tasks_from_backend(
                user_id, cluster_id, processing_tasks
            )
            if started_tasks := [
                current
                for previous, current in changed_tasks
                if current.state is RunningState.STARTED
                or (
                    previous.state in WAITING_FOR_START_STATES
                    and current.state in COMPLETED_STATES
                )
            ]:
                await self._process_started_tasks(
                    started_tasks,
                    user_id=user_id,
                    iteration=iteration,
                    run_metadata=run_metadata,
                )

            if completed_tasks := [
                current
                for _, current in changed_tasks
                if current.state in COMPLETED_STATES
            ]:
                await self._process_completed_tasks(
                    user_id, cluster_id, completed_tasks, run_metadata, iteration
                )

            if incomplete_tasks := [
                current
                for _, current in changed_tasks
                if current.state not in COMPLETED_STATES
            ]:
                await self._process_incomplete_tasks(incomplete_tasks)

            # resource tracking for running tasks
            if running_tasks := [
                task for task in processing_tasks if task.state in RUNNING_STATES
            ]:
                await asyncio.gather(
                    *(
                        publish_service_resource_tracking_heartbeat(
                            self.rabbitmq_client,
                            get_resource_tracking_run_id(
                                user_id, t.project_id, iteration
                            ),
                        )
                        for t in running_tasks
                    )
                )

    @abstractmethod
    async def _start_tasks(
        self,
        *,
        user_id: UserID,
        project_id: ProjectID,
        cluster_id: ClusterID,
        run_metadata: MetadataDict,
        scheduled_tasks: dict[NodeID, Image],
    ) -> None:
        ...

    @abstractmethod
    async def _get_tasks_status(
        self, user_id: UserID, cluster_id: ClusterID, tasks: list[CompTaskAtDB]
    ) -> list[RunningState]:
        ...

    @abstractmethod
    async def _stop_tasks(
        self, user_id: UserID, cluster_id: ClusterID, tasks: list[CompTaskAtDB]
    ) -> None:
        ...

    @abstractmethod
    async def _process_completed_tasks(
        self,
        user_id: UserID,
        cluster_id: ClusterID,
        tasks: list[CompTaskAtDB],
        run_metadata: MetadataDict,
        iteration: Iteration,
    ) -> None:
        ...

    async def _schedule_pipeline(
        self,
        *,
        user_id: UserID,
        project_id: ProjectID,
        cluster_id: ClusterID,
        iteration: PositiveInt,
        marked_for_stopping: bool,
        run_metadata: MetadataDict,
    ) -> None:
        _logger.debug(
            "checking run of project [%s:%s] for user [%s]",
            f"{project_id=}",
            f"{iteration=}",
            f"{user_id=}",
        )

        try:
            dag: nx.DiGraph = await self._get_pipeline_dag(project_id)
            # 1. Update our list of tasks with data from backend (state, results)
            await self._update_states_from_comp_backend(
                user_id, cluster_id, project_id, iteration, dag, run_metadata
            )
            # 2. Any task following a FAILED task shall be ABORTED
            comp_tasks = await self._set_states_following_failed_to_aborted(
                project_id, dag
            )
            # 3. do we want to stop the pipeline now?
            if marked_for_stopping:
                await self._schedule_tasks_to_stop(
                    user_id, project_id, cluster_id, comp_tasks
                )
            else:
                # let's get the tasks to schedule then
                await self._schedule_tasks_to_start(
                    user_id=user_id,
                    project_id=project_id,
                    cluster_id=cluster_id,
                    comp_tasks=comp_tasks,
                    dag=dag,
                    run_metadata=run_metadata,
                )
            # 4. Update the run result
            pipeline_result = await self._update_run_result_from_tasks(
                user_id, project_id, iteration, comp_tasks
            )
            # 5. Are we done scheduling that pipeline?
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

    async def _schedule_tasks_to_stop(
        self,
        user_id: UserID,
        project_id: ProjectID,
        cluster_id: ClusterID,
        comp_tasks: dict[str, CompTaskAtDB],
    ) -> None:
        # get any running task and stop them
        comp_tasks_repo = CompTasksRepository.instance(self.db_engine)
        await comp_tasks_repo.mark_project_published_tasks_as_aborted(project_id)
        # stop any remaining running task, these are already submitted
        tasks_to_stop = [t for t in comp_tasks.values() if t.state in PROCESSING_STATES]
        await self._stop_tasks(user_id, cluster_id, tasks_to_stop)

    async def _schedule_tasks_to_start(
        self,
        user_id: UserID,
        project_id: ProjectID,
        cluster_id: ClusterID,
        run_metadata: MetadataDict,
        comp_tasks: dict[str, CompTaskAtDB],
        dag: nx.DiGraph,
    ):
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
            node_id: comp_tasks[f"{node_id}"]
            for node_id in next_task_node_ids
            if comp_tasks[f"{node_id}"].state == RunningState.PUBLISHED
        }

        if not tasks_ready_to_start:
            # nothing to do
            return

        # Change the tasks state to PENDING
        comp_tasks_repo = CompTasksRepository.instance(self.db_engine)
        await comp_tasks_repo.update_project_tasks_state(
            project_id,
            list(tasks_ready_to_start.keys()),
            RunningState.PENDING,
            optional_progress=0,
            optional_started=arrow.utcnow().datetime,
        )

        # we pass the tasks to the dask-client in a gather such that each task can be stopped independently
        results = await asyncio.gather(
            *[
                self._start_tasks(
                    user_id=user_id,
                    project_id=project_id,
                    cluster_id=cluster_id,
                    run_metadata=run_metadata,
                    scheduled_tasks={node_id: task.image},
                )
                for node_id, task in tasks_ready_to_start.items()
            ],
            return_exceptions=True,
        )
        # Handling errors raised when _start_tasks(...)
        for r, t in zip(results, tasks_ready_to_start, strict=True):
            if isinstance(r, TaskSchedulingError):
                _logger.error(
                    "Project '%s''s task '%s' could not be scheduled due to the following: %s",
                    r.project_id,
                    r.node_id,
                    f"{r}",
                )

                await comp_tasks_repo.update_project_tasks_state(
                    project_id,
                    [r.node_id],
                    RunningState.FAILED,
                    r.get_errors(),
                    optional_progress=1.0,
                    optional_stopped=arrow.utcnow().datetime,
                )
            elif isinstance(
                r,
                ComputationalBackendNotConnectedError
                | ComputationalSchedulerChangedError,
            ):
                _logger.error(
                    "Issue with computational backend: %s. Tasks are set back "
                    "to PUBLISHED state until scheduler comes back!",
                    r,
                )
                # we should try re-connecting.
                # in the meantime we cannot schedule tasks on the scheduler,
                # let's put these tasks back to PUBLISHED, so they might be re-submitted later
                await asyncio.gather(
                    comp_tasks_repo.update_project_tasks_state(
                        project_id,
                        list(tasks_ready_to_start.keys()),
                        RunningState.PUBLISHED,
                        optional_progress=0,
                    ),
                )
            elif isinstance(r, Exception):
                _logger.error(
                    "Unexpected error for %s with %s on %s happened when scheduling %s:\n%s\n%s",
                    f"{user_id=}",
                    f"{project_id=}",
                    f"{cluster_id=}",
                    f"{tasks_ready_to_start.keys()=}",
                    f"{r}",
                    "".join(traceback.format_tb(r.__traceback__)),
                )
                await comp_tasks_repo.update_project_tasks_state(
                    project_id,
                    [t],
                    RunningState.FAILED,
                    optional_progress=1.0,
                    optional_stopped=arrow.utcnow().datetime,
                )

    def _wake_up_scheduler_now(self) -> None:
        self.wake_up_event.set()
