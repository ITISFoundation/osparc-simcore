import logging
from datetime import datetime

from aiohttp import web
from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.users import GroupID, UserID
from pydantic import BaseModel, parse_obj_as
from simcore_service_webserver.projects.models import UserProjectAccessRights

from ..users import api as users_api
from . import _groups_db as projects_groups_db
from ._groups_db import ProjectGroupGetDB
from .db import APP_PROJECT_DBAPI, ProjectDBAPI
from .exceptions import ProjectInvalidRightsError

log = logging.getLogger(__name__)


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
    product_name: ProductName,  # pylint: disable=unused-argument
) -> ProjectGroupGet:
    project_db: ProjectDBAPI = app[APP_PROJECT_DBAPI]

    project_access_rights: UserProjectAccessRights = (
        await project_db.get_project_access_rights_for_user(
            user_id=user_id, project_uuid=project_id  # add product_name
        )
    )
    if project_access_rights.write is False:
        raise ProjectInvalidRightsError(
            user_id=user_id,
            project_uuid=project_id,
            reason=f"User does not have write access to project {project_id}",
        )

    project_group_db: ProjectGroupGetDB = await projects_groups_db.create_project_group(
        app=app,
        project_id=project_id,
        group_id=group_id,
        read=read,
        write=write,
        delete=delete,
    )
    project_group_api: ProjectGroupGet = ProjectGroupGet(**project_group_db.dict())

    return project_group_api


async def list_project_groups_by_user_and_project(
    app: web.Application,
    *,
    user_id: UserID,
    project_id: ProjectID,
    product_name: ProductName,  # pylint: disable=unused-argument
) -> list[ProjectGroupGet]:
    project_db: ProjectDBAPI = app[APP_PROJECT_DBAPI]

    project_access_rights: UserProjectAccessRights = (
        await project_db.get_project_access_rights_for_user(
            user_id=user_id, project_uuid=project_id  # add product_name
        )
    )
    if project_access_rights.read is False:
        raise ProjectInvalidRightsError(
            user_id=user_id,
            project_uuid=project_id,
            reason=f"User does not have read access to project {project_id}",
        )

    project_groups_db: list[
        ProjectGroupGetDB
    ] = await projects_groups_db.list_project_groups(app=app, project_id=project_id)

    project_groups_api: list[ProjectGroupGet] = [
        parse_obj_as(ProjectGroupGet, group) for group in project_groups_db
    ]

    return project_groups_api


async def update_project_group(
    app: web.Application,
    *,
    user_id: UserID,
    project_id: ProjectID,
    group_id: GroupID,
    read: bool,
    write: bool,
    delete: bool,
    product_name: ProductName,  # pylint: disable=unused-argument
) -> ProjectGroupGet:
    project_db: ProjectDBAPI = app[APP_PROJECT_DBAPI]

    project_access_rights: UserProjectAccessRights = (
        await project_db.get_project_access_rights_for_user(
            user_id=user_id, project_uuid=project_id  # add product_name
        )
    )
    if project_access_rights.write is False:
        raise ProjectInvalidRightsError(
            user_id=user_id,
            project_uuid=project_id,
            reason=f"User does not have write access to project {project_id}",
        )

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

    project_group_db: ProjectGroupGetDB = await projects_groups_db.update_project_group(
        app=app,
        project_id=project_id,
        group_id=group_id,
        read=read,
        write=write,
        delete=delete,
    )

    project_api: ProjectGroupGet = ProjectGroupGet(**project_group_db.dict())
    return project_api


async def delete_project_group(
    app: web.Application,
    *,
    user_id: UserID,
    project_id: ProjectID,
    group_id: GroupID,
    product_name: ProductName,  # pylint: disable=unused-argument
) -> None:
    project_db: ProjectDBAPI = app[APP_PROJECT_DBAPI]

    project_access_rights: UserProjectAccessRights = (
        await project_db.get_project_access_rights_for_user(
            user_id=user_id, project_uuid=project_id  # add product_name
        )
    )
    if project_access_rights.delete is False:
        raise ProjectInvalidRightsError(
            user_id=user_id,
            project_uuid=project_id,
            reason=f"User does not have delete access to project {project_id}",
        )
    project = await project_db.get_project_db(project_id)
    project_owner_user: dict = await users_api.get_user(app, project.prj_owner)
    if project_owner_user["primary_gid"] == group_id:
        user: dict = await users_api.get_user(app, user_id)
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
