import logging
from dataclasses import dataclass
from typing import Callable, Dict, List

from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from simcore_service_director_v2.core.settings import CelerySchedulerSettings
from simcore_service_director_v2.modules.comp_scheduler.base_scheduler import (
    BaseCompScheduler,
)

from ...models.domains.comp_tasks import CompTaskAtDB, Image
from ...models.schemas.constants import ClusterID, UserID
from ...modules.celery import CeleryClient

logger = logging.getLogger(__name__)


@dataclass
class CeleryScheduler(BaseCompScheduler):
    settings: CelerySchedulerSettings
    celery_client: CeleryClient

    async def _start_tasks(
        self,
        user_id: UserID,
        project_id: ProjectID,
        _cluster_id: ClusterID,
        scheduled_tasks: Dict[NodeID, Image],
        callback: Callable[[], None],
    ):
        # notify the sidecar they should start now
        self.celery_client.send_computation_tasks(
            user_id=user_id,
            project_id=project_id,
            tasks=scheduled_tasks,
            callback=callback,
        )

    async def _stop_tasks(self, tasks: List[CompTaskAtDB]) -> None:
        self.celery_client.abort_computation_tasks([str(t.job_id) for t in tasks])
