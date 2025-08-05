from aiohttp import web
from models_library.projects import ProjectID
from models_library.projects_nodes import Node
from models_library.projects_nodes_io import NodeID
from models_library.services_types import ServiceKey, ServiceVersion
from pydantic import TypeAdapter
from simcore_postgres_database.utils_projects_nodes import ProjectNodesRepo
from simcore_postgres_database.utils_repos import pass_or_acquire_connection
from simcore_service_webserver.db.plugin import get_asyncpg_engine


async def get_project_nodes_services(
    app: web.Application, *, project_uuid: ProjectID
) -> list[tuple[ServiceKey, ServiceVersion]]:
    repo = ProjectNodesRepo(project_uuid=project_uuid)

    async with pass_or_acquire_connection(get_asyncpg_engine(app)) as conn:
        project_nodes = await repo.list(conn)

    # removes duplicates by preserving order
    return list(dict.fromkeys((node.key, node.version) for node in project_nodes))


async def get_project_nodes_map(
    app: web.Application, *, project_id: ProjectID
) -> dict[NodeID, Node]:

    repo = ProjectNodesRepo(project_uuid=project_id)

    async with pass_or_acquire_connection(get_asyncpg_engine(app)) as conn:
        project_nodes = await repo.list(conn)

    workbench = {
        project_node.node_id: project_node.model_dump_as_node()
        for project_node in project_nodes
    }
    return TypeAdapter(dict[NodeID, Node]).validate_python(workbench)
