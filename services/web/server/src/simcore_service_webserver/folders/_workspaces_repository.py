import logging

from aiohttp import web
from models_library.folders import FolderID
from models_library.products import ProductName
from models_library.users import UserID
from models_library.workspaces import WorkspaceID
from simcore_postgres_database.utils_repos import transaction_context

from ..db.plugin import get_asyncpg_engine
from ..projects import _folders_repository as projects_folders_repository
from ..projects import _groups_repository as projects_groups_repository
from ..projects._access_rights_service import check_user_project_permission
from ..projects.api import patch_project_and_notify_users
from ..users import users_service
from ..workspaces.api import check_user_workspace_access
from . import _folders_repository

_logger = logging.getLogger(__name__)


async def move_folder_into_workspace(
    app: web.Application,
    *,
    user_id: UserID,
    folder_id: FolderID,
    workspace_id: WorkspaceID | None,
    product_name: ProductName,
    client_session_id: str | None = None,
) -> None:
    # 1. User needs to have delete permission on source folder
    folder_db = await _folders_repository.get(
        app, folder_id=folder_id, product_name=product_name
    )
    workspace_is_private = True
    if folder_db.workspace_id:
        await check_user_workspace_access(
            app,
            user_id=user_id,
            workspace_id=folder_db.workspace_id,
            product_name=product_name,
            permission="delete",
        )
        workspace_is_private = False

    # 2. User needs to have write permission on destination workspace
    if workspace_id is not None:
        await check_user_workspace_access(
            app,
            user_id=user_id,
            workspace_id=workspace_id,
            product_name=product_name,
            permission="write",
        )

    # 3. User needs to have delete permission on all the projects inside source folder
    (
        folder_ids,
        project_ids,
    ) = await _folders_repository.get_all_folders_and_projects_ids_recursively(
        app,
        connection=None,
        folder_id=folder_id,
        private_workspace_user_id_or_none=user_id if workspace_is_private else None,
        product_name=product_name,
    )
    # NOTE: Not the most effective, can be improved
    for project_id in project_ids:
        await check_user_project_permission(
            app,
            project_id=project_id,
            user_id=user_id,
            product_name=product_name,
            permission="delete",
        )

    # ⬆️ Here we have already guaranties that user has all the right permissions to do this operation ⬆️

    user: dict = await users_service.get_user(app, user_id)
    async with transaction_context(get_asyncpg_engine(app)) as conn:
        # 4. Update workspace ID on the project resource
        for project_id in project_ids:
            await patch_project_and_notify_users(
                app=app,
                project_uuid=project_id,
                patch_project_data={"workspace_id": workspace_id},
                user_primary_gid=user["primary_gid"],
                client_session_id=client_session_id,
            )

        # 5. BATCH update of folders with workspace_id
        await _folders_repository.update(
            app,
            connection=conn,
            folders_id_or_ids=set(folder_ids),
            product_name=product_name,
            workspace_id=workspace_id,  # <-- Updating workspace_id
            user_id=user_id if workspace_id is None else None,  # <-- Updating user_id
        )

        # 6. Update source folder parent folder ID with NULL (it will appear in the root directory)
        await _folders_repository.update(
            app,
            connection=conn,
            folders_id_or_ids=folder_id,
            product_name=product_name,
            parent_folder_id=None,  # <-- Updating parent folder ID
        )

        # 7. Remove all records of project to folders that are not in the folders that we are moving
        # (ex. If we are moving from private workspace, the same project can be in different folders for different users)
        await projects_folders_repository.delete_all_project_to_folder_by_project_ids_not_in_folder_ids(
            app,
            connection=conn,
            project_id_or_ids=set(project_ids),
            not_in_folder_ids=set(folder_ids),
        )

        # 8. Update the user id field for the remaining folders
        await projects_folders_repository.update_project_to_folder(
            app,
            connection=conn,
            folders_id_or_ids=set(folder_ids),
            user_id=user_id if workspace_id is None else None,  # <-- Updating user_id
        )

        # 9. Remove all project permissions, leave only the user who moved the project
        for project_id in project_ids:
            await projects_groups_repository.delete_all_project_groups(
                app, connection=conn, project_id=project_id
            )
            await projects_groups_repository.update_or_insert_project_group(
                app,
                connection=conn,
                project_id=project_id,
                group_id=user["primary_gid"],
                read=True,
                write=True,
                delete=True,
            )
