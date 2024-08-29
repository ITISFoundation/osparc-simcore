import logging

from aiohttp import web
from models_library.folders import FolderID
from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.users import UserID
from simcore_service_webserver.projects._access_rights_api import (
    get_user_project_access_rights,
)

from . import _folders_db as project_to_folders_db
from .db import APP_PROJECT_DBAPI, ProjectDBAPI
from .exceptions import ProjectInvalidRightsError

_logger = logging.getLogger(__name__)


async def move_project_to_folder(
    app: web.Application,
    *,
    user_id: UserID,
    project_id: ProjectID,
    folder_id: FolderID | None,
    product_name: ProductName,
) -> None:
    project_api: ProjectDBAPI = app[APP_PROJECT_DBAPI]
    project_db = await project_api.get_project_db(project_id)
    _private_workspace_user_id: UserID | None = user_id
    if project_db.workspace_id is not None:
        # If not in personal workspace, check whether you have permission to move
        project_access_rights = await get_user_project_access_rights(
            app, project_id=project_id, user_id=user_id, product_name=product_name
        )
        if project_access_rights.write is False:
            raise ProjectInvalidRightsError(
                user_id=user_id,
                project_uuid=project_id,
                reason=f"User does not have write access to project {project_id}",
            )
        # Setup folder user id to None, as this is not a private workspace
        _private_workspace_user_id = None
    # Move
    prj_to_folder_db = await project_to_folders_db.get_project_to_folder(
        app, project_id=project_id, user_id=_private_workspace_user_id
    )
    if prj_to_folder_db is None:
        if folder_id is None:
            return
        await project_to_folders_db.insert_project_to_folder(
            app,
            project_id=project_id,
            folder_id=folder_id,
            user_id=_private_workspace_user_id,
        )
    else:
        # Delete old
        await project_to_folders_db.delete_project_to_folder(
            app,
            project_id=project_id,
            folder_id=prj_to_folder_db.folder_id,
            user_id=_private_workspace_user_id,
        )
        # Create new
        if folder_id is not None:
            await project_to_folders_db.insert_project_to_folder(
                app,
                project_id=project_id,
                folder_id=folder_id,
                user_id=_private_workspace_user_id,
            )
