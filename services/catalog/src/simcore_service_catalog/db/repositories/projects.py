import logging
from typing import List

import sqlalchemy as sa
from models_library.services import ServiceKeyVersion
from pydantic import ValidationError

from ..tables import ProjectType, projects
from ._base import BaseRepository

logger = logging.getLogger(__name__)


class ProjectsRepository(BaseRepository):
    async def list_services_from_published_templates(self) -> List[ServiceKeyVersion]:
        list_of_published_services: List[ServiceKeyVersion] = []
        async with self.db_engine.connect() as conn:
            async for row in conn.execute(
                sa.select([projects]).where(
                    (projects.c.type == ProjectType.TEMPLATE)
                    & (projects.c.published == True)
                )
            ):
                project_workbench = row.workbench
                for node in project_workbench:
                    service = project_workbench[node]
                    try:
                        if (
                            "file-picker" in service["key"]
                            or "nodes-group" in service["key"]
                        ):
                            # these 2 are not going to pass the validation tests, they are frontend only nodes.
                            continue
                        list_of_published_services.append(ServiceKeyVersion(**service))
                    except ValidationError:
                        logger.warning(
                            "service %s could not be validated", service, exc_info=True
                        )
                        continue

        return list_of_published_services
