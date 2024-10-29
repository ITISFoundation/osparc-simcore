import logging
from datetime import datetime

from aiohttp import web
from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.users import GroupID, UserID
from pydantic import BaseModel

from ..users import api as users_api
from . import _groups_db as projects_groups_db
from ._access_rights_api import check_user_project_permission
from ._groups_db import ProjectGroupGetDB
from .db import APP_PROJECT_DBAPI, ProjectDBAPI
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

    project_groups_db: list[
        ProjectGroupGetDB
    ] = await projects_groups_db.list_project_groups(app=app, project_id=project_id)

    project_groups_api: list[ProjectGroupGet] = [
        ProjectGroupGet.model_validate(group.model_dump()) for group in project_groups_db
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
