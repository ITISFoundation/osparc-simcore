from aiohttp import web
from models_library.projects import ProjectID
from models_library.services_types import ServiceKey, ServiceVersion
from simcore_postgres_database.utils_projects_nodes import ProjectNode, ProjectNodesRepo
from simcore_postgres_database.utils_repos import pass_or_acquire_connection

from ..db.plugin import get_asyncpg_engine


async def get_project_nodes_services(
    app: web.Application, *, project_uuid: ProjectID
) -> list[tuple[ServiceKey, ServiceVersion]]:
    repo = ProjectNodesRepo(project_uuid=project_uuid)

    async with pass_or_acquire_connection(get_asyncpg_engine(app)) as conn:
        nodes = await repo.list(conn)

    # removes duplicates by preserving order
    return list(dict.fromkeys((node.key, node.version) for node in nodes))


async def get_project_nodes(app: web.Application, *, project_uuid: ProjectID) -> list[ProjectNode]:
    repo = ProjectNodesRepo(project_uuid=project_uuid)

    async with pass_or_acquire_connection(get_asyncpg_engine(app)) as conn:
        return await repo.list(conn)
