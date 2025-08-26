from aiohttp import web
from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.users import UserID

from ..db.plugin import get_database_engine_legacy
from ..workspaces.api import get_workspace
from ._access_rights_repository import get_project_owner
from ._projects_repository_legacy import APP_PROJECT_DBAPI, ProjectDBAPI
from ._projects_repository_legacy_utils import PermissionStr
from .exceptions import ProjectInvalidRightsError, ProjectNotFoundError
from .models import UserProjectAccessRightsWithWorkspace


async def validate_project_ownership(
    app: web.Application, user_id: UserID, project_uuid: ProjectID
):
    """
    Raises:
        ProjectInvalidRightsError: if 'user_id' does not own 'project_uuid'
    """
    if (
        await get_project_owner(
            get_database_engine_legacy(app), project_uuid=project_uuid
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
    product_name: ProductName,
    user_id: UserID,
    project_id: ProjectID,
    permission: PermissionStr = "read",
) -> UserProjectAccessRightsWithWorkspace:
    _user_project_access_rights = await get_user_project_access_rights(
        app, project_id=project_id, user_id=user_id, product_name=product_name
    )
    if getattr(_user_project_access_rights, permission, False) is False:
        raise ProjectInvalidRightsError(user_id=user_id, project_uuid=project_id)
    return _user_project_access_rights
