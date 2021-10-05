import json
import logging
from dataclasses import dataclass
from typing import Callable, Dict, List

from dask_task_models_library.container_tasks.events import (
    TaskLogEvent,
    TaskProgressEvent,
    TaskStateEvent,
)
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID

from ...core.settings import DaskSchedulerSettings
from ...models.domains.comp_tasks import CompTaskAtDB, Image
from ...models.schemas.constants import ClusterID, UserID
from ...modules.dask_client import DaskClient
from ...utils.dask import parse_dask_job_id
from ...utils.scheduler import get_repository
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
        await self.dask_client.send_computation_tasks(
            user_id=user_id,
            project_id=project_id,
            cluster_id=cluster_id,
            tasks=scheduled_tasks,
            callback=callback,
            task_change_handler=self._task_state_change_handler,
        )

    async def _stop_tasks(self, tasks: List[CompTaskAtDB]) -> None:
        await self.dask_client.abort_computation_tasks([str(t.job_id) for t in tasks])

    async def _reconnect_backend(self) -> None:
        await self.dask_client.reconnect_client()

    async def _task_state_change_handler(self, event: str) -> None:
        task_state_event = TaskStateEvent.parse_raw(event)
        logger.debug(
            "received task state update: %s",
            task_state_event,
        )
        *_, project_id, node_id = parse_dask_job_id(task_state_event.job_id)

        comp_tasks_repo: CompTasksRepository = get_repository(
            self.db_engine, CompTasksRepository
        )  # type: ignore
        await comp_tasks_repo.set_project_tasks_state(
            project_id, [node_id], task_state_event.state
        )

    async def _task_progress_change_handler(self, event: str) -> None:
        # FIXME: this must go to the rabbitMQ, and also maybe only construct to save time?
        task_progress_event = TaskProgressEvent.parse_raw(event)
        logger.debug("received task progress update: %s", task_progress_event)
        *_, user_id, project_id, node_id = parse_dask_job_id(task_progress_event.job_id)
        message = {
            "user_id": user_id,
            "project_id": project_id,
            "node_id": node_id,
            "progress": task_progress_event.progress,
            "channel": "progress",
        }
        await self.rabbitmq_client.publish_message(
            task_progress_event.topic_name(), json.dumps(message)
        )

    async def _task_log_change_handler(self, event: str) -> None:
        # FIXME: this must go to the rabbitMQ, and also maybe only construct to save time?
        task_log_event = TaskLogEvent.parse_raw(event)
        logger.debug("received task log update: %s", task_log_event)
        *_, user_id, project_id, node_id = parse_dask_job_id(task_log_event.job_id)
        message = {
            "user_id": user_id,
            "project_id": project_id,
            "node_id": node_id,
            "messages": [task_log_event.log],
            "channel": "logger",
        }
        await self.rabbitmq_client.publish_message(
            task_log_event.topic_name(), json.dumps(message)
        )
