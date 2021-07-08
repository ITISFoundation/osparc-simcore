import logging
from typing import Dict, List, cast

from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID

from ...core.settings import DaskSchedulerSettings
from ...models.domains.comp_tasks import CompTaskAtDB
from ...models.schemas.constants import UserID
from ...modules.dask_client import DaskClient, DaskTaskIn
from ...utils.scheduler import get_repository
from ..db.repositories.comp_tasks import CompTasksRepository
from .base_scheduler import BaseCompScheduler

logger = logging.getLogger(__name__)


class DaskScheduler(BaseCompScheduler):
    settings: DaskSchedulerSettings
    dask_client: DaskClient

    async def _start_tasks(
        self,
        user_id: UserID,
        project_id: ProjectID,
        comp_tasks: Dict[str, CompTaskAtDB],
        tasks: List[NodeID],
    ):
        # get tasks runtime requirements
        dask_tasks: List[DaskTaskIn] = [
            DaskTaskIn.from_node_image(node_id, comp_tasks[f"{node_id}"].image)
            for node_id in tasks
        ]

        # The sidecar only pick up tasks that are in PENDING state
        comp_tasks_repo: CompTasksRepository = cast(
            CompTasksRepository, get_repository(self.db_engine, CompTasksRepository)
        )
        await comp_tasks_repo.mark_project_tasks_as_pending(project_id, tasks)
        # now transfer the pipeline to the dask scheduler
        self.dask_client.send_computation_tasks(
            user_id=user_id,
            project_id=project_id,
            single_tasks=dask_tasks,
            _callback=self._wake_up_scheduler_now,
        )
