import logging

from aiohttp import web
from models_library.api_schemas_webserver.projects_groups import ProjectGroupGet
from models_library.groups import GroupID
from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.users import UserID

from ..db.plugin import get_database_engine
from ..users import api as users_api
from ..workspaces.api import get_workspace
from . import _access_rights_repository
from . import _access_rights_repository as projects_groups_db
from ._access_rights_repository import ProjectGroupGetDB
from ._projects_repository_legacy import APP_PROJECT_DBAPI, ProjectDBAPI
from .exceptions import ProjectInvalidRightsError, ProjectNotFoundError
from .models import PermissionStr, UserProjectAccessRightsWithWorkspace

_logger = logging.getLogger(__name__)


async def validate_project_ownership(
    app: web.Application, user_id: UserID, project_uuid: ProjectID
):
    """
    Raises:
        ProjectInvalidRightsError: if 'user_id' does not own 'project_uuid'
    """
    if (
        await _access_rights_repository.get_project_owner(
            get_database_engine(app), project_uuid=project_uuid
        )
        != user_id
    ):
        raise ProjectInvalidRightsError(user_id=user_id, project_uuid=project_uuid)


async def get_user_project_access_rights(
    app: web.Application,
    project_id: ProjectID,
    user_id: UserID,
    product_name: ProductName,
) -> UserProjectAccessRightsWithWorkspace:
    """
    This function resolves user access rights on the project resource.

    If project belongs to user private workspace (workspace_id = None) then it is resolved
    via user <--> groups <--> projects_to_groups.

    If project belongs to shared workspace (workspace_id not None) then it is resolved
    via user <--> groups <--> workspace_access_rights
    """
    db: ProjectDBAPI = app[APP_PROJECT_DBAPI]

    project_db = await db.get_project_db(project_id)
    if project_db.workspace_id:
        workspace = await get_workspace(
            app,
            user_id=user_id,
            workspace_id=project_db.workspace_id,
            product_name=product_name,
        )
        _user_project_access_rights_with_workspace = (
            UserProjectAccessRightsWithWorkspace(
                uid=user_id,
                workspace_id=project_db.workspace_id,
                read=workspace.my_access_rights.read,
                write=workspace.my_access_rights.write,
                delete=workspace.my_access_rights.delete,
            )
        )
    else:
        _user_project_access_rights = (
            await db.get_pure_project_access_rights_without_workspace(
                user_id, project_id
            )
        )
        _user_project_access_rights_with_workspace = (
            UserProjectAccessRightsWithWorkspace(
                uid=user_id,
                workspace_id=None,
                read=_user_project_access_rights.read,
                write=_user_project_access_rights.write,
                delete=_user_project_access_rights.delete,
            )
        )
    return _user_project_access_rights_with_workspace


async def has_user_project_access_rights(
    app: web.Application,
    *,
    project_id: ProjectID,
    user_id: UserID,
    permission: PermissionStr,
) -> bool:
    try:
        db: ProjectDBAPI = app[APP_PROJECT_DBAPI]
        product_name = await db.get_project_product(project_uuid=project_id)

        prj_access_rights = await get_user_project_access_rights(
            app, project_id=project_id, user_id=user_id, product_name=product_name
        )
        return getattr(prj_access_rights, permission, False) is not False
    except (ProjectInvalidRightsError, ProjectNotFoundError):
        return False


async def check_user_project_permission(
    app: web.Application,
    *,
    project_id: ProjectID,
    user_id: UserID,
    product_name: ProductName,
    permission: PermissionStr = "read",
) -> UserProjectAccessRightsWithWorkspace:
    _user_project_access_rights = await get_user_project_access_rights(
        app, project_id=project_id, user_id=user_id, product_name=product_name
    )
    if getattr(_user_project_access_rights, permission, False) is False:
        raise ProjectInvalidRightsError(user_id=user_id, project_uuid=project_id)
    return _user_project_access_rights


### CRUD with groups in projects


async def create_project_group(
    app: web.Application,
    *,
    user_id: UserID,
    project_id: ProjectID,
    group_id: GroupID,
    read: bool,
    write: bool,
    delete: bool,
    product_name: ProductName,
) -> ProjectGroupGet:
    await check_user_project_permission(
        app,
        project_id=project_id,
        user_id=user_id,
        product_name=product_name,
        permission="write",
    )

    project_group_db: ProjectGroupGetDB = await projects_groups_db.create_project_group(
        app=app,
        project_id=project_id,
        group_id=group_id,
        read=read,
        write=write,
        delete=delete,
    )
    project_group_api: ProjectGroupGet = ProjectGroupGet(
        **project_group_db.model_dump()
    )

    return project_group_api


async def list_project_groups_by_user_and_project(
    app: web.Application,
    *,
    user_id: UserID,
    project_id: ProjectID,
    product_name: ProductName,
) -> list[ProjectGroupGet]:
    await check_user_project_permission(
        app,
        project_id=project_id,
        user_id=user_id,
        product_name=product_name,
        permission="read",
    )

    project_groups_db: list[ProjectGroupGetDB] = (
        await projects_groups_db.list_project_groups(app=app, project_id=project_id)
    )

    project_groups_api: list[ProjectGroupGet] = [
        ProjectGroupGet.model_validate(group.model_dump())
        for group in project_groups_db
    ]

    return project_groups_api


async def replace_project_group(
    app: web.Application,
    *,
    user_id: UserID,
    project_id: ProjectID,
    group_id: GroupID,
    read: bool,
    write: bool,
    delete: bool,
    product_name: ProductName,
) -> ProjectGroupGet:
    await check_user_project_permission(
        app,
        project_id=project_id,
        user_id=user_id,
        product_name=product_name,
        permission="write",
    )

    project_db: ProjectDBAPI = app[APP_PROJECT_DBAPI]
    project = await project_db.get_project_db(project_id)
    project_owner_user: dict = await users_api.get_user(app, project.prj_owner)
    if project_owner_user["primary_gid"] == group_id:
        user: dict = await users_api.get_user(app, user_id)
        if user["primary_gid"] != project_owner_user["primary_gid"]:
            # Only the owner of the project can modify the owner group
            raise ProjectInvalidRightsError(
                user_id=user_id,
                project_uuid=project_id,
                reason=f"User does not have access to modify owner project group in project {project_id}",
            )

    project_group_db: ProjectGroupGetDB = (
        await projects_groups_db.replace_project_group(
            app=app,
            project_id=project_id,
            group_id=group_id,
            read=read,
            write=write,
            delete=delete,
        )
    )

    project_api: ProjectGroupGet = ProjectGroupGet(**project_group_db.model_dump())
    return project_api


async def delete_project_group(
    app: web.Application,
    *,
    user_id: UserID,
    project_id: ProjectID,
    group_id: GroupID,
    product_name: ProductName,
) -> None:
    user: dict = await users_api.get_user(app, user_id=user_id)
    if user["primary_gid"] != group_id:
        await check_user_project_permission(
            app,
            project_id=project_id,
            user_id=user_id,
            product_name=product_name,
            permission="delete",
        )

    project_db: ProjectDBAPI = app[APP_PROJECT_DBAPI]
    project = await project_db.get_project_db(project_id)
    project_owner_user: dict = await users_api.get_user(app, project.prj_owner)
    if project_owner_user["primary_gid"] == group_id:
        if user["primary_gid"] != project_owner_user["primary_gid"]:
            # Only the owner of the project can delete the owner group
            raise ProjectInvalidRightsError(
                user_id=user_id,
                project_uuid=project_id,
                reason=f"User does not have access to modify owner project group in project {project_id}",
            )

    await projects_groups_db.delete_project_group(
        app=app, project_id=project_id, group_id=group_id
    )


### Operations without checking permissions


async def delete_project_group_without_checking_permissions(
    app: web.Application,
    *,
    project_id: ProjectID,
    group_id: GroupID,
) -> None:
    await projects_groups_db.delete_project_group(
        app=app, project_id=project_id, group_id=group_id
    )


async def create_project_group_without_checking_permissions(
    app: web.Application,
    *,
    project_id: ProjectID,
    group_id: GroupID,
    read: bool,
    write: bool,
    delete: bool,
) -> None:
    await projects_groups_db.update_or_insert_project_group(
        app=app,
        project_id=project_id,
        group_id=group_id,
        read=read,
        write=write,
        delete=delete,
    )
