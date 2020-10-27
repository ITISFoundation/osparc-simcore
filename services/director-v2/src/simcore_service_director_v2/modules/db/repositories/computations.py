import logging
from datetime import datetime
from typing import Dict, Tuple

import sqlalchemy as sa
from ....models.domains.comp_tasks import CompTaskAtDB
from models_library.projects import NodeID, ProjectID, RunningState

from ..tables import NodeClass, comp_tasks
from ._base import BaseRepository

logger = logging.getLogger(__name__)


class CompPipelinesRepository(BaseRepository):
    pass


class CompTasksRepository(BaseRepository):
    async def get_comp_tasks(
        self,
        project_id: ProjectID,
    ) -> Dict[NodeID, CompTaskAtDB]:
        tasks: Dict[NodeID, CompTaskAtDB] = {}
        async for row in self.connection.execute(
            sa.select([comp_tasks]).where(
                (comp_tasks.c.project_id == str(project_id))
                & (comp_tasks.c.node_class == NodeClass.COMPUTATIONAL)
            )
        ):
            task_db = CompTaskAtDB(**row)
            tasks[task_db.node_id] = task_db

        return tasks
