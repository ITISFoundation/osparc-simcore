import datetime
from typing import Final

from aiohttp import web
from models_library.projects import ProjectID
from models_library.users import UserID
from pydantic import NonNegativeFloat, NonNegativeInt

from ..application_settings import get_settings
from .projects_exceptions import ProjectStartsTooManyDynamicNodes

_NODE_START_INTERVAL_S: Final[datetime.timedelta] = datetime.timedelta(seconds=15)


def get_service_start_lock_key(user_id: UserID, project_uuid: ProjectID) -> str:
    return f"lock_service_start_limit.{user_id}.{project_uuid}"


def check_num_service_per_projects_limit(
    app: web.Application,
    number_of_services: int,
    user_id: UserID,
    project_uuid: ProjectID,
) -> None:
    """
    raises ProjectStartsTooManyDynamicNodes if the user cannot start more services
    """
    project_settings = get_settings(app).WEBSERVER_PROJECTS
    assert project_settings  # nosec
    if project_settings.PROJECTS_MAX_NUM_RUNNING_DYNAMIC_NODES > 0 and (
        number_of_services >= project_settings.PROJECTS_MAX_NUM_RUNNING_DYNAMIC_NODES
    ):
        raise ProjectStartsTooManyDynamicNodes(
            user_id=user_id, project_uuid=project_uuid
        )


def get_total_project_dynamic_nodes_creation_interval(
    max_nodes: NonNegativeInt,
) -> NonNegativeFloat:
    """
    Estimated amount of time for all project node creation requests to be sent to the
    director-v2. Note: these calls are sent one after the other.
    """
    return max_nodes * _NODE_START_INTERVAL_S.total_seconds()
