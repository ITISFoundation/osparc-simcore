import asyncio
import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import AsyncIterator

from dask_task_models_library.container_tasks.errors import TaskCancelledError
from dask_task_models_library.container_tasks.events import (
    TaskLogEvent,
    TaskProgressEvent,
    TaskStateEvent,
)
from dask_task_models_library.container_tasks.io import TaskOutputData
from models_library.clusters import DEFAULT_CLUSTER_ID, Cluster, ClusterID
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.projects_state import RunningState
from models_library.rabbitmq_messages import (
    InstrumentationRabbitMessage,
    LoggerRabbitMessage,
    ProgressRabbitMessageNode,
)
from models_library.users import UserID
from servicelib.common_headers import UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE
from simcore_postgres_database.models.comp_tasks import NodeClass
from simcore_service_director_v2.core.errors import TaskSchedulingError

from ...core.settings import ComputationalBackendSettings
from ...models.domains.comp_tasks import CompTaskAtDB, Image
from ...modules.dask_client import DaskClient, TaskHandlers
from ...modules.dask_clients_pool import DaskClientsPool
from ...modules.db.repositories.clusters import ClustersRepository
from ...utils.dask import (
    clean_task_output_and_log_files_if_invalid,
    parse_dask_job_id,
    parse_output_data,
)
from ...utils.scheduler import get_repository
from ..db.repositories.comp_tasks import CompTasksRepository
from ..rabbitmq import RabbitMQClient
from .base_scheduler import BaseCompScheduler

logger = logging.getLogger(__name__)


@asynccontextmanager
async def _cluster_dask_client(
    user_id: UserID, cluster_id: ClusterID, scheduler: "DaskScheduler"
) -> AsyncIterator[DaskClient]:
    cluster: Cluster = scheduler.settings.default_cluster
    if cluster_id != DEFAULT_CLUSTER_ID:
        clusters_repo: ClustersRepository = get_repository(
            scheduler.db_engine, ClustersRepository
        )  # type: ignore
        cluster = await clusters_repo.get_cluster(user_id, cluster_id)
    async with scheduler.dask_clients_pool.acquire(cluster) as client:
        yield client


@dataclass
class DaskScheduler(BaseCompScheduler):
    settings: ComputationalBackendSettings
    dask_clients_pool: DaskClientsPool
    rabbitmq_client: RabbitMQClient

    def __post_init__(self):
        self.dask_clients_pool.register_handlers(
            TaskHandlers(
                self._task_state_change_handler,
                self._task_progress_change_handler,
                self._task_log_change_handler,
            )
        )

    async def _start_tasks(
        self,
        user_id: UserID,
        project_id: ProjectID,
        cluster_id: ClusterID,
        scheduled_tasks: dict[NodeID, Image],
    ):
        # now transfer the pipeline to the dask scheduler
        async with _cluster_dask_client(user_id, cluster_id, self) as client:
            task_job_ids: list[
                tuple[NodeID, str]
            ] = await client.send_computation_tasks(
                user_id=user_id,
                project_id=project_id,
                cluster_id=cluster_id,
                tasks=scheduled_tasks,
                callback=self._wake_up_scheduler_now,
            )
            logger.debug(
                "started following tasks (node_id, job_id)[%s] on cluster %s",
                f"{task_job_ids=}",
                f"{cluster_id=}",
            )
        # update the database so we do have the correct job_ids there
        comp_tasks_repo: CompTasksRepository = get_repository(
            self.db_engine, CompTasksRepository
        )  # type: ignore
        await asyncio.gather(
            *[
                comp_tasks_repo.set_project_task_job_id(project_id, node_id, job_id)
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

    async def _process_completed_tasks(
        self, user_id: UserID, cluster_id: ClusterID, tasks: list[CompTaskAtDB]
    ) -> None:
        try:
            async with _cluster_dask_client(user_id, cluster_id, self) as client:
                tasks_results = await asyncio.gather(
                    *[client.get_task_result(t.job_id or "undefined") for t in tasks],
                    return_exceptions=True,
                )
            await asyncio.gather(
                *[
                    self._process_task_result(task, result)
                    for task, result in zip(tasks, tasks_results)
                ]
            )
        finally:
            async with _cluster_dask_client(user_id, cluster_id, self) as client:
                await asyncio.gather(
                    *[client.release_task_result(t.job_id) for t in tasks if t.job_id]
                )

    async def _process_task_result(
        self, task: CompTaskAtDB, result: Exception | TaskOutputData
    ) -> None:
        logger.debug("received %s result: %s", f"{task=}", f"{result=}")
        task_final_state = RunningState.FAILED
        errors = None

        if task.job_id is not None:
            (
                service_key,
                service_version,
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
                    # we need to remove any invalid files in the storage
                    await clean_task_output_and_log_files_if_invalid(
                        self.db_engine, user_id, project_id, node_id
                    )
            except TaskSchedulingError as err:
                task_final_state = RunningState.FAILED
                errors = err.get_errors()
                logger.debug(
                    "Unexpected failure while processing results of %s: %s",
                    f"{task=}",
                    f"{errors=}",
                )

            # instrumentation
            message = InstrumentationRabbitMessage.construct(
                metrics="service_stopped",
                user_id=user_id,
                project_id=task.project_id,
                node_id=task.node_id,
                service_uuid=task.node_id,
                service_type=NodeClass.COMPUTATIONAL.value,
                service_key=service_key,
                service_tag=service_version,
                result=task_final_state,
                simcore_user_agent=UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE,
            )
            await self.rabbitmq_client.publish(message.channel_name, message.json())

        await CompTasksRepository(self.db_engine).set_project_tasks_state(
            task.project_id, [task.node_id], task_final_state, errors=errors
        )

    async def _task_state_change_handler(self, event: str) -> None:
        task_state_event = TaskStateEvent.parse_raw(event)
        logger.debug(
            "received task state update: %s",
            task_state_event,
        )
        service_key, service_version, user_id, project_id, node_id = parse_dask_job_id(
            task_state_event.job_id
        )

        if task_state_event.state == RunningState.STARTED:
            message = InstrumentationRabbitMessage.construct(
                metrics="service_started",
                user_id=user_id,
                project_id=project_id,
                node_id=node_id,
                service_uuid=node_id,
                service_type=NodeClass.COMPUTATIONAL.value,
                service_key=service_key,
                service_tag=service_version,
                simcore_user_agent=UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE,
            )
            await self.rabbitmq_client.publish(message.channel_name, message.json())

        await CompTasksRepository(self.db_engine).set_project_tasks_state(
            project_id, [node_id], task_state_event.state
        )

    async def _task_progress_change_handler(self, event: str) -> None:
        task_progress_event = TaskProgressEvent.parse_raw(event)
        logger.debug("received task progress update: %s", task_progress_event)
        *_, user_id, project_id, node_id = parse_dask_job_id(task_progress_event.job_id)
        message = ProgressRabbitMessageNode.construct(
            user_id=user_id,
            project_id=project_id,
            node_id=node_id,
            progress=task_progress_event.progress,
        )
        await self.rabbitmq_client.publish(message.channel_name, message.json())

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

        await self.rabbitmq_client.publish(message.channel_name, message.json())
