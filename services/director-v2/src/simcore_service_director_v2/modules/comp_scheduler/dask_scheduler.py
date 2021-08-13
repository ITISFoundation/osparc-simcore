import logging
from dataclasses import dataclass
from typing import Callable, Dict, List

from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID

from ...core.settings import DaskSchedulerSettings
from ...models.domains.comp_tasks import CompTaskAtDB
from ...models.schemas.constants import UserID
from ...models.schemas.services import NodeRequirements
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
        scheduled_tasks: Dict[NodeID, NodeRequirements],
        callback: Callable[[], None],
    ):
        # now transfer the pipeline to the dask scheduler
        self.dask_client.send_computation_tasks(
            user_id=user_id,
            project_id=project_id,
            single_tasks=scheduled_tasks,
            callback=callback,
        )

    async def _stop_tasks(self, tasks: List[CompTaskAtDB]) -> None:
        self.dask_client.abort_computation_tasks([str(t.job_id) for t in tasks])
