import asyncio
import logging
from dataclasses import dataclass
from typing import Callable, Dict, List, Tuple

from dask_task_models_library.container_tasks.events import (
    TaskLogEvent,
    TaskProgressEvent,
    TaskStateEvent,
)
from dask_task_models_library.container_tasks.io import TaskOutputData
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.projects_state import RunningState
from models_library.rabbitmq_messages import (
    InstrumentationRabbitMessage,
    LoggerRabbitMessage,
    ProgressRabbitMessage,
)
from simcore_postgres_database.models.comp_tasks import NodeClass

from ...core.settings import DaskSchedulerSettings
from ...models.domains.comp_tasks import CompTaskAtDB, Image
from ...models.schemas.constants import ClusterID, UserID
from ...modules.dask_client import DaskClient
from ...utils.dask import (
    clean_task_output_and_log_files_if_invalid,
    parse_dask_job_id,
    parse_output_data,
)
from ...utils.scheduler import COMPLETED_STATES, get_repository
from ..db.repositories.comp_tasks import CompTasksRepository
from ..rabbitmq import RabbitMQClient
from .base_scheduler import BaseCompScheduler

logger = logging.getLogger(__name__)


@dataclass
class DaskScheduler(BaseCompScheduler):
    settings: DaskSchedulerSettings
    dask_client: DaskClient
    rabbitmq_client: RabbitMQClient

    def __post_init__(self):
        self.dask_client.register_handlers(
            task_change_handler=self._task_state_change_handler,
            task_progress_handler=self._task_progress_change_handler,
            task_log_handler=self._task_log_change_handler,
        )

    async def _start_tasks(
        self,
        user_id: UserID,
        project_id: ProjectID,
        cluster_id: ClusterID,
        scheduled_tasks: Dict[NodeID, Image],
        callback: Callable[[], None],
    ):
        # now transfer the pipeline to the dask scheduler
        task_job_ids: List[
            Tuple[NodeID, str]
        ] = await self.dask_client.send_computation_tasks(
            user_id=user_id,
            project_id=project_id,
            cluster_id=cluster_id,
            tasks=scheduled_tasks,
            callback=self._on_task_completed,
        )
        logger.debug("started following tasks (node_id, job_id)[%s]", task_job_ids)
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

    async def _stop_tasks(self, tasks: List[CompTaskAtDB]) -> None:
        await self.dask_client.abort_computation_tasks([f"{t.job_id}" for t in tasks])

    async def _reconnect_backend(self) -> None:
        app = self.dask_client.app
        client_settings = self.dask_client.settings
        await self.dask_client.delete()
        self.dask_client = await DaskClient.create(app, client_settings)
        self.dask_client.register_handlers(
            task_change_handler=self._task_state_change_handler,
            task_progress_handler=self._task_progress_change_handler,
            task_log_handler=self._task_log_change_handler,
        )

    async def _on_task_completed(self, event: TaskStateEvent) -> None:
        logger.debug(
            "received task completion: %s",
            event,
        )
        service_key, service_version, user_id, project_id, node_id = parse_dask_job_id(
            event.job_id
        )

        assert event.state in COMPLETED_STATES  # nosec

        logger.info(
            "task %s completed with state: %s",
            event.job_id,
            f"{event.state.value}".lower(),
        )
        if event.state == RunningState.SUCCESS:
            # we need to parse the results
            assert event.msg  # nosec
            await parse_output_data(
                self.db_engine,
                event.job_id,
                TaskOutputData.parse_raw(event.msg),
            )
        else:
            # we need to remove any invalid files in the storage
            await clean_task_output_and_log_files_if_invalid(
                self.db_engine, user_id, project_id, node_id
            )

        await CompTasksRepository(self.db_engine).set_project_tasks_state(
            project_id, [node_id], event.state
        )
        # instrumentation
        message = InstrumentationRabbitMessage(
            metrics="service_stopped",
            user_id=user_id,
            project_id=project_id,
            node_id=node_id,
            service_uuid=node_id,
            service_type=NodeClass.COMPUTATIONAL,
            service_key=service_key,
            service_tag=service_version,
            result=event.state,
        )
        await self.rabbitmq_client.publish_message(message)
        self._wake_up_scheduler_now()

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
            message = InstrumentationRabbitMessage(
                metrics="service_started",
                user_id=user_id,
                project_id=project_id,
                node_id=node_id,
                service_uuid=node_id,
                service_type=NodeClass.COMPUTATIONAL,
                service_key=service_key,
                service_tag=service_version,
            )
            await self.rabbitmq_client.publish_message(message)

        await CompTasksRepository(self.db_engine).set_project_tasks_state(
            project_id, [node_id], task_state_event.state
        )

    async def _task_progress_change_handler(self, event: str) -> None:
        task_progress_event = TaskProgressEvent.parse_raw(event)
        logger.debug("received task progress update: %s", task_progress_event)
        *_, user_id, project_id, node_id = parse_dask_job_id(task_progress_event.job_id)
        message = ProgressRabbitMessage(
            user_id=user_id,
            project_id=project_id,
            node_id=node_id,
            progress=task_progress_event.progress,
        )
        await self.rabbitmq_client.publish_message(message)

    async def _task_log_change_handler(self, event: str) -> None:
        task_log_event = TaskLogEvent.parse_raw(event)
        logger.debug("received task log update: %s", task_log_event)
        *_, user_id, project_id, node_id = parse_dask_job_id(task_log_event.job_id)
        message = LoggerRabbitMessage(
            user_id=user_id,
            project_id=project_id,
            node_id=node_id,
            messages=[task_log_event.log],
        )

        await self.rabbitmq_client.publish_message(message)
