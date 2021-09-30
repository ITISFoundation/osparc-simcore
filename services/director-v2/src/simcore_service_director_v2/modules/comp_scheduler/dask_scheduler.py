import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Dict, List, Tuple

from dask_task_models_library.container_tasks.events import TaskStateEvent
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID

from ...core.settings import DaskSchedulerSettings
from ...models.domains.comp_tasks import CompTaskAtDB, Image
from ...models.schemas.constants import ClusterID, UserID
from ...modules.dask_client import DaskClient
from ...utils.dask import parse_dask_job_id
from ...utils.scheduler import get_repository
from ..db.repositories.comp_tasks import CompTasksRepository
from .base_scheduler import BaseCompScheduler

logger = logging.getLogger(__name__)


@dataclass
class DaskScheduler(BaseCompScheduler):
    settings: DaskSchedulerSettings
    dask_client: DaskClient

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

    async def _task_state_change_handler(self, event: Tuple[str, str]) -> None:
        timestamp, json_message = event
        task_state_event = TaskStateEvent.parse_raw(json_message)
        logger.warning(
            "received task state update: [%s]: %s",
            datetime.fromtimestamp(float(timestamp)),
            task_state_event,
        )
        *_, project_id, node_id = parse_dask_job_id(task_state_event.job_id)

        comp_tasks_repo: CompTasksRepository = get_repository(
            self.db_engine, CompTasksRepository
        )  # type: ignore
        await comp_tasks_repo.set_project_tasks_state(
            project_id, [node_id], task_state_event.state
        )
