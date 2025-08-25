import logging

from aiohttp import web
from models_library.folders import FolderID
from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.users import UserID

from ..folders import _folders_repository as folders_folders_repository
from . import _folders_repository
from ._access_rights_service import get_user_project_access_rights
from ._projects_repository_legacy import APP_PROJECT_DBAPI, ProjectDBAPI
from .exceptions import ProjectInvalidRightsError

_logger = logging.getLogger(__name__)


async def move_project_into_folder(
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

    # In private workspace user can move as he wish, but in the
    # shared workspace user needs to have write permission
    workspace_is_private = True
    if project_db.workspace_id is not None:  # shared workspace
        if project_access_rights.write is False:
            raise ProjectInvalidRightsError(
                user_id=user_id,
                project_uuid=project_id,
                details=f"User does not have write access to project {project_id}",
            )
        workspace_is_private = False

    private_workspace_user_id_or_none: UserID | None = (
        user_id if workspace_is_private else None
    )

    if folder_id:
        # Check user has access to folder
        await folders_folders_repository.get_for_user_or_workspace(
            app,
            folder_id=folder_id,
            product_name=product_name,
            user_id=private_workspace_user_id_or_none,
            workspace_id=project_db.workspace_id,
        )

    # Move project to folder
    prj_to_folder_db = await _folders_repository.get_project_to_folder(
        app,
        project_id=project_id,
        private_workspace_user_id_or_none=private_workspace_user_id_or_none,
    )
    if prj_to_folder_db is None:
        if folder_id is None:
            return
        await _folders_repository.insert_project_to_folder(
            app,
            project_id=project_id,
            folder_id=folder_id,
            private_workspace_user_id_or_none=private_workspace_user_id_or_none,
        )
    else:
        # Delete old
        await _folders_repository.delete_project_to_folder(
            app,
            project_id=project_id,
            folder_id=prj_to_folder_db.folder_id,
            private_workspace_user_id_or_none=private_workspace_user_id_or_none,
        )
        # Create new
        if folder_id is not None:
            await _folders_repository.insert_project_to_folder(
                app,
                project_id=project_id,
                folder_id=folder_id,
                private_workspace_user_id_or_none=private_workspace_user_id_or_none,
            )
