from aiohttp import web
from models_library.api_schemas_webserver.projects_metadata import MetadataDict
from models_library.projects import ProjectID
from models_library.users import UserID


async def get_project_custom_metadata(
    app: web.Application, user_id: UserID, project_id: ProjectID
) -> MetadataDict:
    # check if user_id has access to get
    # check if project_id exists
    # get metadata
    raise NotImplementedError


async def set_project_custom_metadata(
    app: web.Application, user_id: UserID, project_id: ProjectID, value: MetadataDict
) -> MetadataDict:
    raise NotImplementedError
