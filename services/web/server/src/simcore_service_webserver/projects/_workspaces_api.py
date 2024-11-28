import logging

from aiohttp import web
from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.users import UserID
from models_library.workspaces import WorkspaceID

from ..projects._access_rights_api import get_user_project_access_rights
from ..users.api import get_user
from ..workspaces.api import check_user_workspace_access
from . import _db_v2 as project_db_v2
from . import _folders_db as project_to_folders_db
from . import _groups_db as project_groups_db
from .db import APP_PROJECT_DBAPI, ProjectDBAPI
from .exceptions import ProjectInvalidRightsError

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
        raise ProjectInvalidRightsError(user_id=user_id, project_uuid=project_id)

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
    await project_db_v2.patch_project(
        app=app,
        project_uuid=project_id,
        new_partial_project_data={"workspace_id": workspace_id},
    )
    # NOTE: MD: should I also patch the project owner? -> probably yes, or if it is more like "original owner" then probably no

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
