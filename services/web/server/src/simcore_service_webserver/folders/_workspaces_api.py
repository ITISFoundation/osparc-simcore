import logging

from aiohttp import web
from models_library.access_rights import AccessRights
from models_library.folders import FolderID
from models_library.products import ProductName
from models_library.users import UserID
from models_library.workspaces import WorkspaceID

from ..users.api import get_user
from ..workspaces.api import check_user_workspace_access
from . import _folders_db

_logger = logging.getLogger(__name__)


async def move_folder_into_workspace(
    app: web.Application,
    *,
    user_id: UserID,
    folder_id: FolderID,
    workspace_id: WorkspaceID | None,
    product_name: ProductName,
) -> None:
    # 1. User needs to have delete permission on source folder
    folder_db = await _folders_db.get(
        app, folder_id=folder_id, product_name=product_name
    )
    workspace_is_private = True
    user_folder_access_rights = AccessRights(read=True, write=True, delete=True)
    if folder_db.workspace_id:
        user_workspace_access_rights = await check_user_workspace_access(
            app,
            user_id=user_id,
            workspace_id=folder_db.workspace_id,
            product_name=product_name,
            permission="delete",
        )
        workspace_is_private = False
        user_folder_access_rights = user_workspace_access_rights.my_access_rights

    # Here we have checked user has delete access rights on the folder he is moving

    # 2.  User needs to have write permission on destination workspace
    if workspace_id is not None:
        user_workspace_access_rights = await check_user_workspace_access(
            app,
            user_id=user_id,
            workspace_id=workspace_id,
            product_name=product_name,
            permission="write",
        )

    # Here we have already guaranties that user has all the right permissions to do this operation

    # Get all project children
    # await _folders_db.
    # Get all folder children
    children_folders_list = await _folders_db.get_folders_recursively(
        app, connection=None, folder_id=folder_id, product_name=product_name
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

    # 5. Remove all project permissions, leave only the user who moved the project
    user = await get_user(app, user_id=user_id)
    await project_groups_db.delete_all_project_groups(app, project_id=project_id)
    await project_groups_db.update_or_insert_project_group(
        app,
        project_id=project_id,
        group_id=user["primary_gid"],
        read=True,
        write=True,
        delete=True,
    )
