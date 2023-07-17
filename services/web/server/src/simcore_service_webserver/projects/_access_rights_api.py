from aiohttp import web
from models_library.projects import ProjectID
from models_library.users import UserID

from ..db.plugin import get_database_engine
from ._access_rights_db import get_project_owner
from .exceptions import ProjectInvalidRightsError


async def validate_project_ownership(
    app: web.Application, user_id: UserID, project_uuid: ProjectID
):
    """
    Raises:
        ProjectInvalidRightsError: if 'user_id' does not own 'project_uuid'
    """
    if (
        await get_project_owner(get_database_engine(app), project_uuid=project_uuid)
        != user_id
    ):
        raise ProjectInvalidRightsError(user_id=user_id, project_uuid=project_uuid)
