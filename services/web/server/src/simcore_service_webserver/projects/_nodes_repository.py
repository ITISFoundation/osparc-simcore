from aiohttp import web
from models_library.projects import ProjectID
from models_library.services_types import ServiceKey, ServiceVersion
from simcore_postgres_database.utils_projects_nodes import ProjectNodesRepo

from ..db.plugin import get_database_engine


async def get_project_nodes_services(
    app: web.Application, *, project_uuid: ProjectID
) -> list[tuple[ServiceKey, ServiceVersion]]:
    repo = ProjectNodesRepo(project_uuid=project_uuid)

    async with get_database_engine(app).acquire() as conn:
        nodes = await repo.list(conn)

    # removes duplicates by preserving order
    return list(dict.fromkeys((node.key, node.version) for node in nodes))
