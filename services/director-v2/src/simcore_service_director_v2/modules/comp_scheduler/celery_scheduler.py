import logging
from dataclasses import dataclass
from typing import Dict, List, Optional

from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from simcore_service_director_v2.core.settings import CelerySchedulerSettings
from simcore_service_director_v2.modules.comp_scheduler.base_scheduler import (
    BaseCompScheduler,
)

from ...models.domains.comp_tasks import CompTaskAtDB
from ...models.schemas.constants import UserID
from ...modules.celery import CeleryClient, CeleryTaskIn
from ...utils.scheduler import get_repository
from ..db.repositories.comp_tasks import CompTasksRepository

logger = logging.getLogger(__name__)


@dataclass
class CeleryScheduler(BaseCompScheduler):
    settings: CelerySchedulerSettings
    celery_client: CeleryClient

    async def _start_tasks(
        self,
        user_id: UserID,
        project_id: ProjectID,
        comp_tasks: Dict[str, CompTaskAtDB],
        tasks: List[NodeID],
    ):
        # get tasks runtime requirements
        celery_tasks: List[CeleryTaskIn] = [
            CeleryTaskIn.from_node_image(node_id, comp_tasks[f"{node_id}"].image)
            for node_id in tasks
        ]

        # The sidecar only pick up tasks that are in PENDING state
        comp_tasks_repo: CompTasksRepository = get_repository(
            self.db_engine, CompTasksRepository
        )  # type: ignore
        await comp_tasks_repo.mark_project_tasks_as_pending(project_id, tasks)
        # notify the sidecar they should start now
        self.celery_client.send_computation_tasks(
            user_id=user_id,
            project_id=project_id,
            single_tasks=celery_tasks,
            callback=self._wake_up_scheduler_now,
        )

    async def _stop_task(self, tasks: List[NodeID]) -> None:
        pass
