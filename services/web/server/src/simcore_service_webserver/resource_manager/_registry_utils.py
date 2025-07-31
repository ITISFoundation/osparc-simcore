import logging

from models_library.projects import ProjectID

from .registry import RedisResourceRegistry

_logger = logging.getLogger(__name__)


async def list_opened_project_ids(registry: RedisResourceRegistry) -> list[ProjectID]:
    """Lists all project IDs that are currently opened in active sessions."""
    opened_projects: list[ProjectID] = []
    all_session_alive, _ = await registry.get_all_resource_keys()
    for alive_session in all_session_alive:
        resources = await registry.get_resources(alive_session)
        if projects_id := resources.get("project_id"):
            opened_projects.append(ProjectID(projects_id))
    return opened_projects
