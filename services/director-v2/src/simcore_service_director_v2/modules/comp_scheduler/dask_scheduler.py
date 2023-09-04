import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

import arrow
from dask_task_models_library.container_tasks.errors import TaskCancelledError
from dask_task_models_library.container_tasks.events import (
    TaskLogEvent,
    TaskProgressEvent,
)
from dask_task_models_library.container_tasks.io import TaskOutputData
from models_library.clusters import DEFAULT_CLUSTER_ID, Cluster, ClusterID
from models_library.errors import ErrorDict
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.projects_state import RunningState
from models_library.rabbitmq_messages import (
    LoggerRabbitMessage,
    ProgressRabbitMessageNode,
    SimcorePlatformStatus,
)
from models_library.users import UserID
from servicelib.common_headers import UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE

from ...core.errors import TaskSchedulingError
from ...models.comp_runs import RunMetadataDict
from ...models.comp_tasks import CompTaskAtDB, Image
from ...modules.dask_client import DaskClient
from ...modules.dask_clients_pool import DaskClientsPool
from ...modules.db.repositories.clusters import ClustersRepository
from ...utils.comp_scheduler import Iteration, get_resource_tracking_run_id
from ...utils.dask import (
    clean_task_output_and_log_files_if_invalid,
    parse_dask_job_id,
    parse_output_data,
)
from ...utils.dask_client_utils import TaskHandlers
from ...utils.rabbitmq import (
    publish_service_resource_tracking_stopped,
    publish_service_stopped_metrics,
)
from ..db.repositories.comp_tasks import CompTasksRepository
from .base_scheduler import BaseCompScheduler, ScheduledPipelineParams

logger = logging.getLogger(__name__)


@asynccontextmanager
async def _cluster_dask_client(
    user_id: UserID, cluster_id: ClusterID, scheduler: "DaskScheduler"
) -> AsyncIterator[DaskClient]:
    cluster: Cluster = scheduler.settings.default_cluster
    if cluster_id != DEFAULT_CLUSTER_ID:
        clusters_repo = ClustersRepository.instance(scheduler.db_engine)
        cluster = await clusters_repo.get_cluster(user_id, cluster_id)
    async with scheduler.dask_clients_pool.acquire(cluster) as client:
        yield client


@dataclass
class DaskScheduler(BaseCompScheduler):
    dask_clients_pool: DaskClientsPool

    def __post_init__(self):
        self.dask_clients_pool.register_handlers(
            TaskHandlers(
                self._task_progress_change_handler,
                self._task_log_change_handler,
            )
        )

    async def _start_tasks(
        self,
        *,
        user_id: UserID,
        project_id: ProjectID,
        scheduled_tasks: dict[NodeID, Image],
        pipeline_params: ScheduledPipelineParams,
    ):
        # now transfer the pipeline to the dask scheduler
        async with _cluster_dask_client(
            user_id, pipeline_params.cluster_id, self
        ) as client:
            task_job_ids: list[
                tuple[NodeID, str]
            ] = await client.send_computation_tasks(
                user_id=user_id,
                project_id=project_id,
                cluster_id=pipeline_params.cluster_id,
                tasks=scheduled_tasks,
                callback=self._wake_up_scheduler_now,
                metadata=pipeline_params.run_metadata,
            )
            logger.debug(
                "started following tasks (node_id, job_id)[%s] on cluster %s",
                f"{task_job_ids=}",
                f"{pipeline_params.cluster_id=}",
            )
        # update the database so we do have the correct job_ids there
        comp_tasks_repo = CompTasksRepository.instance(self.db_engine)
        await asyncio.gather(
            *[
                comp_tasks_repo.update_project_task_job_id(project_id, node_id, job_id)
                for node_id, job_id in task_job_ids
            ]
        )

    async def _get_tasks_status(
        self, user_id: UserID, cluster_id: ClusterID, tasks: list[CompTaskAtDB]
    ) -> list[RunningState]:
        async with _cluster_dask_client(user_id, cluster_id, self) as client:
            return await client.get_tasks_status([f"{t.job_id}" for t in tasks])

    async def _stop_tasks(
        self, user_id: UserID, cluster_id: ClusterID, tasks: list[CompTaskAtDB]
    ) -> None:
        async with _cluster_dask_client(user_id, cluster_id, self) as client:
            await asyncio.gather(
                *[client.abort_computation_task(t.job_id) for t in tasks if t.job_id]
            )
            # tasks that have no-worker must be unpublished as these are blocking forever
            tasks_with_no_worker = [
                t for t in tasks if t.state is RunningState.WAITING_FOR_RESOURCES
            ]
            await asyncio.gather(
                *[
                    client.release_task_result(t.job_id)
                    for t in tasks_with_no_worker
                    if t.job_id
                ]
            )

    async def _process_completed_tasks(
        self,
        user_id: UserID,
        cluster_id: ClusterID,
        tasks: list[CompTaskAtDB],
        run_metadata: RunMetadataDict,
        iteration: Iteration,
    ) -> None:
        try:
            async with _cluster_dask_client(user_id, cluster_id, self) as client:
                tasks_results = await asyncio.gather(
                    *[client.get_task_result(t.job_id or "undefined") for t in tasks],
                    return_exceptions=True,
                )
            await asyncio.gather(
                *[
                    self._process_task_result(task, result, run_metadata, iteration)
                    for task, result in zip(tasks, tasks_results, strict=True)
                ]
            )
        finally:
            async with _cluster_dask_client(user_id, cluster_id, self) as client:
                await asyncio.gather(
                    *[client.release_task_result(t.job_id) for t in tasks if t.job_id]
                )

    async def _process_task_result(
        self,
        task: CompTaskAtDB,
        result: Exception | TaskOutputData,
        run_metadata: RunMetadataDict,
        iteration: Iteration,
    ) -> None:
        logger.debug("received %s result: %s", f"{task=}", f"{result=}")
        task_final_state = RunningState.FAILED
        simcore_platform_status = SimcorePlatformStatus.OK
        errors: list[ErrorDict] = []

        if task.job_id is not None:
            (
                _service_key,
                _service_version,
                user_id,
                project_id,
                node_id,
            ) = parse_dask_job_id(task.job_id)

            assert task.project_id == project_id  # nosec
            assert task.node_id == node_id  # nosec

            try:
                if isinstance(result, TaskOutputData):
                    # success!
                    await parse_output_data(
                        self.db_engine,
                        task.job_id,
                        result,
                    )
                    task_final_state = RunningState.SUCCESS

                else:
                    if isinstance(result, TaskCancelledError):
                        task_final_state = RunningState.ABORTED
                    else:
                        task_final_state = RunningState.FAILED
                        errors.append(
                            {
                                "loc": (
                                    f"{task.project_id}",
                                    f"{task.node_id}",
                                ),
                                "msg": f"{result}",
                                "type": "runtime",
                            }
                        )
                    # we need to remove any invalid files in the storage
                    await clean_task_output_and_log_files_if_invalid(
                        self.db_engine, user_id, project_id, node_id
                    )
            except TaskSchedulingError as err:
                task_final_state = RunningState.FAILED
                simcore_platform_status = SimcorePlatformStatus.BAD
                errors = err.get_errors()
                logger.debug(
                    "Unexpected failure while processing results of %s: %s",
                    f"{task=}",
                    f"{errors=}",
                )

            # resource tracking
            await publish_service_resource_tracking_stopped(
                self.rabbitmq_client,
                get_resource_tracking_run_id(user_id, project_id, node_id, iteration),
                simcore_platform_status=simcore_platform_status,
            )
            # instrumentation
            await publish_service_stopped_metrics(
                self.rabbitmq_client,
                user_id=user_id,
                simcore_user_agent=run_metadata.get(
                    "simcore_user_agent", UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE
                ),
                task=task,
                task_final_state=task_final_state,
            )

        await CompTasksRepository(self.db_engine).update_project_tasks_state(
            task.project_id,
            [task.node_id],
            task_final_state,
            errors=errors,
            optional_progress=1,
            optional_stopped=arrow.utcnow().datetime,
        )

    async def _task_progress_change_handler(self, event: str) -> None:
        task_progress_event = TaskProgressEvent.parse_raw(event)
        logger.debug("received task progress update: %s", task_progress_event)
        *_, user_id, project_id, node_id = parse_dask_job_id(task_progress_event.job_id)

        await CompTasksRepository(self.db_engine).update_project_task_progress(
            project_id, node_id, task_progress_event.progress
        )

        message = ProgressRabbitMessageNode.construct(
            user_id=user_id,
            project_id=project_id,
            node_id=node_id,
            progress=task_progress_event.progress,
        )
        await self.rabbitmq_client.publish(message.channel_name, message)

    async def _task_log_change_handler(self, event: str) -> None:
        task_log_event = TaskLogEvent.parse_raw(event)
        logger.debug("received task log update: %s", task_log_event)
        *_, user_id, project_id, node_id = parse_dask_job_id(task_log_event.job_id)
        message = LoggerRabbitMessage.construct(
            user_id=user_id,
            project_id=project_id,
            node_id=node_id,
            messages=[task_log_event.log],
            log_level=task_log_event.log_level,
        )

        await self.rabbitmq_client.publish(message.channel_name, message)
