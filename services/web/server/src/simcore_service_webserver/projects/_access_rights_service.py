from aiohttp import web
from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.users import UserID
from simcore_postgres_database.models.users import UserRole

from ..db.plugin import get_database_engine_legacy
from ..products import products_service
from ..users import users_service
from ..workspaces.api import get_workspace
from ._access_rights_repository import get_project_owner, is_published_project
from ._projects_repository_legacy import PROJECT_DBAPI_APPKEY, ProjectDBAPI
from ._projects_repository_legacy_utils import PermissionStr
from .exceptions import ProjectInvalidRightsError, ProjectNotFoundError
from .models import UserProjectAccessRightsWithWorkspace


async def validate_project_ownership(app: web.Application, user_id: UserID, project_uuid: ProjectID):
    """
    Raises:
        ProjectInvalidRightsError: if 'user_id' does not own 'project_uuid'
    """
    if await get_project_owner(get_database_engine_legacy(app), project_uuid=project_uuid) != user_id:
        raise ProjectInvalidRightsError(user_id=user_id, project_uuid=project_uuid)


async def _is_published_project_for_product(
    app: web.Application,
    *,
    project_uuid: ProjectID,
    product_name: ProductName,
) -> bool:
    product = products_service.get_product(app, product_name)
    return await is_published_project(
        app,
        project_id=project_uuid,
        product_group_id=product.group_id,
    )


async def _has_guest_project_access(
    app: web.Application,
    *,
    user_id: UserID,
    project_uuid: ProjectID,
    product_name: ProductName,
) -> bool:
    try:
        await validate_project_ownership(app, user_id=user_id, project_uuid=project_uuid)
        return True
    except ProjectInvalidRightsError:
        return await _is_published_project_for_product(
            app,
            project_uuid=project_uuid,
            product_name=product_name,
        )


async def _check_guest_project_permission(
    app: web.Application,
    *,
    user_id: UserID,
    project_uuid: ProjectID,
    product_name: ProductName,
) -> None:
    """Checks special permissions for GUEST users on project within a product

    Raises:
        ProjectInvalidRightsError if user_id does not satisfy special GUEST project permissions
    """
    if not await _has_guest_project_access(
        app,
        user_id=user_id,
        project_uuid=project_uuid,
        product_name=product_name,
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
    db: ProjectDBAPI = app[PROJECT_DBAPI_APPKEY]

    project_db = await db.get_project_db(project_id)
    if project_db.workspace_id:
        workspace = await get_workspace(
            app,
            user_id=user_id,
            workspace_id=project_db.workspace_id,
            product_name=product_name,
        )
        _user_project_access_rights_with_workspace = UserProjectAccessRightsWithWorkspace(
            uid=user_id,
            workspace_id=project_db.workspace_id,
            read=workspace.my_access_rights.read,
            write=workspace.my_access_rights.write,
            delete=workspace.my_access_rights.delete,
        )
    else:
        _user_project_access_rights = await db.get_pure_project_access_rights_without_workspace(user_id, project_id)
        _user_project_access_rights_with_workspace = UserProjectAccessRightsWithWorkspace(
            uid=user_id,
            workspace_id=None,
            read=_user_project_access_rights.read,
            write=_user_project_access_rights.write,
            delete=_user_project_access_rights.delete,
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
        db: ProjectDBAPI = app[PROJECT_DBAPI_APPKEY]
        product_name = await db.get_project_product(project_uuid=project_id)

        user_role = await users_service.get_user_role(app, user_id=user_id)
        if user_role == UserRole.GUEST and not await _has_guest_project_access(
            app,
            user_id=user_id,
            project_uuid=project_id,
            product_name=product_name,
        ):
            return False

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
    """
    Raises:
        ProjectInvalidRightsError: if 'user_id' does not have 'permission' access to 'project_id'
        within this 'product_name'

    Returns:
        UserProjectAccessRightsWithWorkspace: user access rights on the project resource, including workspace_id
        if project belongs to shared workspace
    """
    # GUEST users may only access projects they own or published projects
    user_role = await users_service.get_user_role(app, user_id=user_id)
    if user_role == UserRole.GUEST:
        await _check_guest_project_permission(
            app,
            user_id=user_id,
            project_uuid=project_id,
            product_name=product_name,
        )

    _user_project_access_rights = await get_user_project_access_rights(
        app, project_id=project_id, user_id=user_id, product_name=product_name
    )
    if getattr(_user_project_access_rights, permission, False) is False:
        raise ProjectInvalidRightsError(user_id=user_id, project_uuid=project_id)
    return _user_project_access_rights
