from typing import List

import sqlalchemy as sa
from pydantic import ValidationError

from ...models.domain.service import ServiceKeyVersion
from ..tables import ProjectType, projects
from ._base import BaseRepository


class ProjectsRepository(BaseRepository):
    async def list_services_from_published_templates(self) -> List[ServiceKeyVersion]:
        list_of_published_services: List[ServiceKeyVersion] = []
        async for row in self.connection.execute(
            sa.select([projects]).where(
                (projects.c.type == ProjectType.TEMPLATE)
                & (projects.c.published == True)
            )
        ):
            project_workbench = row.workbench
            for node in project_workbench:
                service = project_workbench[node]
                try:
                    list_of_published_services.append(ServiceKeyVersion(**service))
                except ValidationError:
                    continue

        return list_of_published_services
