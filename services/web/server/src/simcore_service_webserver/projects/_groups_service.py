import hashlib
import logging
from datetime import datetime

import arrow
from aiohttp import web
from models_library.access_rights import AccessRights
from models_library.basic_types import IDStr
from models_library.groups import GroupID
from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.users import UserID
from pydantic import BaseModel, EmailStr, TypeAdapter

from ..users import users_service
from . import _groups_repository
from ._access_rights_service import check_user_project_permission
from ._groups_models import ProjectGroupGetDB
from ._projects_repository_legacy import APP_PROJECT_DBAPI, ProjectDBAPI
from .exceptions import ProjectInvalidRightsError

_logger = logging.getLogger(__name__)


class ProjectGroupGet(BaseModel):
    gid: GroupID
    read: bool
    write: bool
    delete: bool
    created: datetime
    modified: datetime


async def create_project_group(
    app: web.Application,
    *,
    user_id: UserID,
    project_id: ProjectID,
    sharee_group_id: GroupID,
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

    project_group_db: ProjectGroupGetDB = await _groups_repository.create_project_group(
        app=app,
        project_id=project_id,
        group_id=sharee_group_id,
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
        await _groups_repository.list_project_groups(app=app, project_id=project_id)
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
    project_owner_user: dict = await users_service.get_user(app, project.prj_owner)
    if project_owner_user["primary_gid"] == group_id:
        user: dict = await users_service.get_user(app, user_id)
        if user["primary_gid"] != project_owner_user["primary_gid"]:
            # Only the owner of the project can modify the owner group
            raise ProjectInvalidRightsError(
                user_id=user_id,
                project_uuid=project_id,
                details=f"User does not have access to modify owner project group in project {project_id}",
            )

    project_group_db: ProjectGroupGetDB = (
        await _groups_repository.replace_project_group(
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
    user: dict = await users_service.get_user(app, user_id=user_id)
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
    project_owner_user: dict = await users_service.get_user(app, project.prj_owner)
    if (
        project_owner_user["primary_gid"] == group_id
        and user["primary_gid"] != project_owner_user["primary_gid"]
    ):
        # Only the owner of the project can delete the owner group
        raise ProjectInvalidRightsError(
            user_id=user_id,
            project_uuid=project_id,
            details=f"User does not have access to modify owner project group in project {project_id}",
        )

    await _groups_repository.delete_project_group(
        app=app, project_id=project_id, group_id=group_id
    )


async def create_confirmation_action_to_share_project(
    app: web.Application,
    *,
    product_name: ProductName,
    user_id: UserID,  # sharer
    project_id: ProjectID,  # shared
    sharee_email: EmailStr,  # sharee
    # access-rights for sharing
    read: bool,
    write: bool,
    delete: bool,
) -> IDStr:
    assert app  # nosec

    _logger.debug(
        "Checking that %s in %s has enough access rights (i.e. ownership) to %s for sharing",
        f"{user_id=}",
        f"{product_name=}",
        f"{project_id=}",
    )

    sharer_user_id = user_id
    shared_resource_type = "project"
    shared_resource_id = project_id
    shared_resource_access_rights = AccessRights(read=read, write=write, delete=delete)
    shared_at = arrow.utcnow().datetime

    # action will be a wrapper around create_project_group that gets primary_gid from the email
    # action needs to be statically registered

    _logger.debug(
        "Creating confirmation token for action=SHARE with and producing a code:"
        "\n %s," * 6,
        sharer_user_id,
        shared_resource_type,
        shared_resource_id,
        shared_resource_access_rights,
        shared_at,
        sharee_email,
    )

    fake_code = hashlib.sha256(sharee_email.encode()).hexdigest()
    return TypeAdapter(IDStr).validate_python(f"fake{fake_code}")


### Operations without checking permissions


async def delete_project_group_without_checking_permissions(
    app: web.Application,
    *,
    project_id: ProjectID,
    group_id: GroupID,
) -> None:
    await _groups_repository.delete_project_group(
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
    await _groups_repository.update_or_insert_project_group(
        app=app,
        project_id=project_id,
        group_id=group_id,
        read=read,
        write=write,
        delete=delete,
    )
