""" Handlers for CRUD operations on /projects/{*}/tags/{*}

"""

import logging

from aiohttp import web
from models_library.projects import ProjectID
from models_library.users import UserID

from ._access_rights_api import check_user_project_permission
from .db import ProjectDBAPI
from .models import ProjectDict

_logger = logging.getLogger(__name__)


async def add_tag(
    app: web.Application, user_id: UserID, project_uuid: ProjectID, tag_id: int
) -> ProjectDict:
    db: ProjectDBAPI = ProjectDBAPI.get_from_app_context(app)

    product_name = await db.get_project_product(project_uuid)
    await check_user_project_permission(
        app,
        project_id=project_uuid,
        user_id=user_id,
        product_name=product_name,
        permission="write",  # NOTE: before there was only read access necessary
    )

    project: ProjectDict = await db.add_tag(
        project_uuid=f"{project_uuid}", user_id=user_id, tag_id=int(tag_id)
    )
    return project


async def remove_tag(
    app: web.Application, user_id: UserID, project_uuid: ProjectID, tag_id: int
) -> ProjectDict:
    db: ProjectDBAPI = ProjectDBAPI.get_from_app_context(app)

    product_name = await db.get_project_product(project_uuid)
    await check_user_project_permission(
        app,
        project_id=project_uuid,
        user_id=user_id,
        product_name=product_name,
        permission="write",  # NOTE: before there was only read access necessary
    )

    project: ProjectDict = await db.remove_tag(
        project_uuid=f"{project_uuid}", user_id=user_id, tag_id=tag_id
    )
    return project
