import logging

from aiohttp import web
from models_library.folders import FolderID
from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.users import UserID
from simcore_service_webserver.projects._access_rights_api import (
    get_user_project_access_rights,
)

from ..folders import _folders_db as folders_db
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

    # Check access to project
    project_access_rights = await get_user_project_access_rights(
        app, project_id=project_id, user_id=user_id, product_name=product_name
    )

    # In personal workspace user can move as he wish, but in the
    # shared workspace user needs to have write permission
    _personal_workspace_user_id_or_none: UserID | None = user_id
    if project_db.workspace_id is not None:  # shared workspace
        if project_access_rights.write is False:
            raise ProjectInvalidRightsError(
                user_id=user_id,
                project_uuid=project_id,
                reason=f"User does not have write access to project {project_id}",
            )
        # Setup _personal_workspace_user_id_or_none to None, as this is not a personal workspace
        _personal_workspace_user_id_or_none = None

    if folder_id:
        # Check user has access to folder
        await folders_db.get_folder_for_user_or_workspace(
            app,
            folder_id=folder_id,
            product_name=product_name,
            user_id=_personal_workspace_user_id_or_none,
            workspace_id=project_db.workspace_id,
        )

    # Move project to folder
    prj_to_folder_db = await project_to_folders_db.get_project_to_folder(
        app,
        project_id=project_id,
        personal_workspace_user_id_or_none=_personal_workspace_user_id_or_none,
    )
    if prj_to_folder_db is None:
        if folder_id is None:
            return
        await project_to_folders_db.insert_project_to_folder(
            app,
            project_id=project_id,
            folder_id=folder_id,
            personal_workspace_user_id_or_none=_personal_workspace_user_id_or_none,
        )
    else:
        # Delete old
        await project_to_folders_db.delete_project_to_folder(
            app,
            project_id=project_id,
            folder_id=prj_to_folder_db.folder_id,
            personal_workspace_user_id_or_none=_personal_workspace_user_id_or_none,
        )
        # Create new
        if folder_id is not None:
            await project_to_folders_db.insert_project_to_folder(
                app,
                project_id=project_id,
                folder_id=folder_id,
                personal_workspace_user_id_or_none=_personal_workspace_user_id_or_none,
            )
