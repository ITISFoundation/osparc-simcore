import logging

from aiohttp import web
from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.users import UserID
from models_library.workspaces import WorkspaceID
from simcore_postgres_database.utils_repos import transaction_context

from ..db.plugin import get_asyncpg_engine
from ..users import users_service
from ..workspaces.api import check_user_workspace_access
from . import _folders_repository, _groups_repository, _projects_repository
from ._access_rights_service import get_user_project_access_rights
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

    async with transaction_context(get_asyncpg_engine(app)) as conn:
        # 3. Delete project to folders (for everybody)
        await _folders_repository.delete_all_project_to_folder_by_project_id(
            app,
            connection=conn,
            project_id=project_id,
        )

        # 4. Update workspace ID on the project resource
        await _projects_repository.patch_project(
            app=app,
            connection=conn,
            project_uuid=project_id,
            new_partial_project_data={"workspace_id": workspace_id},
        )

        # 5. Remove all project permissions, leave only the user who moved the project
        user = await users_service.get_user(app, user_id=user_id)
        await _groups_repository.delete_all_project_groups(
            app, connection=conn, project_id=project_id
        )
        await _groups_repository.update_or_insert_project_group(
            app,
            connection=conn,
            project_id=project_id,
            group_id=user["primary_gid"],
            read=True,
            write=True,
            delete=True,
        )
