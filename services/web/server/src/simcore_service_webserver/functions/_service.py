# This is where calls to the business logic is done.
# calls to the `projects` interface should be done here.
# calls to _repo.py should also be done here

from aiohttp import web
from models_library.users import UserID
from simcore_service_webserver.projects.models import ProjectDict

from ..projects import projects_service


# example function
async def get_project_from_function(
    app: web.Application,
    function_uuid: str,
    user_id: UserID,
) -> ProjectDict:

    project = await projects_service.get_project_for_user(
        app=app, project_uuid=function_uuid, user_id=user_id
    )
    return project
