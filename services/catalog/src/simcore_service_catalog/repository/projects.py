import logging

import sqlalchemy as sa
from models_library.services import ServiceKeyVersion
from pydantic import ValidationError
from simcore_postgres_database.models.projects import ProjectType, projects
from simcore_postgres_database.models.projects_nodes import projects_nodes

from ._base import BaseRepository

_logger = logging.getLogger(__name__)


_IGNORED_SERVICE_KEYS: set[str] = {
    # NOTE: frontend only nodes
    "simcore/services/frontend/file-picker",
    "simcore/services/frontend/nodes-group",
}


class ProjectsRepository(BaseRepository):
    async def list_services_from_published_templates(self) -> list[ServiceKeyVersion]:
        async with self.db_engine.connect() as conn:
            query = (
                sa.select(projects_nodes.c.key, projects_nodes.c.version)
                .distinct()
                .select_from(
                    projects_nodes.join(
                        projects, projects_nodes.c.project_uuid == projects.c.uuid
                    )
                )
                .where(
                    sa.and_(
                        projects.c.type == ProjectType.TEMPLATE,
                        projects.c.published.is_(True),
                        projects_nodes.c.key.notin_(_IGNORED_SERVICE_KEYS),
                    )
                )
            )

            services = []
            async for row in await conn.stream(query):
                try:
                    service = ServiceKeyVersion.model_validate(
                        row, from_attributes=True
                    )
                    services.append(service)
                except ValidationError:
                    _logger.warning(
                        "service with key=%s and version=%s could not be validated",
                        row.key,
                        row.version,
                        exc_info=True,
                    )

            return services
