import logging

from aiohttp import web
from aiopg.sa.engine import Engine
from models_library.folders import FolderID
from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.users import UserID
from simcore_postgres_database import utils_folders as folders_db
from simcore_service_webserver.projects.models import UserProjectAccessRights

from .._constants import APP_DB_ENGINE_KEY
from ..users.api import get_user
from .db import APP_PROJECT_DBAPI, ProjectDBAPI
from .exceptions import ProjectInvalidRightsError

_logger = logging.getLogger(__name__)


async def replace_project_folder(
    app: web.Application,
    *,
    user_id: UserID,
    project_id: ProjectID,
    folder_id: FolderID,
    product_name: ProductName,
) -> None:
    project_db: ProjectDBAPI = app[APP_PROJECT_DBAPI]
    project_access_rights: UserProjectAccessRights = (
        await project_db.get_project_access_rights_for_user(
            user_id=user_id, project_uuid=project_id
        )
    )
    if project_access_rights.write is False:
        raise ProjectInvalidRightsError(
            user_id=user_id,
            project_uuid=project_id,
            reason=f"User does not have write access to project {project_id}",
        )

    user = await get_user(app, user_id=user_id)
    engine: Engine = app[APP_DB_ENGINE_KEY]
    async with engine.acquire() as connection:
        _source_folder_id = await folders_db.get_project_folder_without_check(
            connection,
            project_uuid=project_id,
        )
        if _source_folder_id is None:
            # NOTE: folder permissions are checked inside the function
            await folders_db.folder_add_project(
                connection,
                product_name=product_name,
                folder_id=folder_id,
                gid=user["primary_gid"],
                project_uuid=project_id,
            )
            return

        # NOTE: folder permissions are checked inside the function
        await folders_db.folder_move_project(
            connection,
            product_name=product_name,
            source_folder_id=_source_folder_id,
            gid=user["primary_gid"],
            project_uuid=project_id,
            destination_folder_id=folder_id,
        )
        return
