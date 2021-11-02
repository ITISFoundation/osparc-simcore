import logging
from dataclasses import dataclass
from typing import Callable, Dict, List

from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID

from ...core.settings import DaskSchedulerSettings
from ...models.domains.comp_tasks import CompTaskAtDB, Image
from ...models.schemas.constants import ClusterID, UserID
from ...modules.dask_client import DaskClient
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
        )

    async def _stop_tasks(self, tasks: List[CompTaskAtDB]) -> None:
        await self.dask_client.abort_computation_tasks([str(t.job_id) for t in tasks])

    async def _reconnect_backend(self) -> None:
        await self.dask_client.reconnect_client()
