import logging

from aiohttp import web
from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.users import UserID
from models_library.workspaces import WorkspaceID

from ..projects._access_rights_api import get_user_project_access_rights
from ..workspaces.api import check_user_workspace_access
from . import _folders_db as project_to_folders_db
from .db import APP_PROJECT_DBAPI, ProjectDBAPI

_logger = logging.getLogger(__name__)


async def move_project_into_workspace(
    app: web.Application,
    *,
    user_id: UserID,
    project_id: ProjectID,
    workspace_id: WorkspaceID | None,
    product_name: ProductName,
) -> None:
    project_api: ProjectDBAPI = app[APP_PROJECT_DBAPI]

    # 1. User needs to have delete permission on project
    project_access_rights = await get_user_project_access_rights(
        app, project_id=project_id, user_id=user_id, product_name=product_name
    )
    if project_access_rights.delete is False:
        raise ValueError("not enough permissions")

    # 2. User needs to have write permission on workspace
    if workspace_id:
        await check_user_workspace_access(
            app,
            user_id=user_id,
            workspace_id=workspace_id,
            product_name=product_name,
            permission="write",
        )

    # 3. Delete project to folders (for everybody)
    await project_to_folders_db.delete_all_project_to_folder_by_project_id(
        app,
        project_id=project_id,
    )

    # 4. Update workspace ID on the project resource
    await project_api.patch_project(
        project_uuid=project_id,
        new_partial_project_data={"workspace_id": workspace_id},
    )
