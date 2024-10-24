import asyncio
import logging
from datetime import timedelta

import arrow
from aiohttp import web
from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.users import UserID

from . import projects_api
from .models import ProjectPatchExtended
from .settings import get_plugin_settings

_logger = logging.getLogger(__name__)


async def empty_trash(app: web.Application, product_name: ProductName, user_id: UserID):
    # filter trashed=True and set them to False
    _logger.debug(
        "CODE PLACEHOLDER: all projects marked of trashed of %s in %s are deleted",
        f"{user_id=}",
        f"{product_name=}",
    )
    raise NotImplementedError


async def prune_all_trashes(app: web.Application) -> list[str]:
    settings = get_plugin_settings(app)
    retention = timedelta(days=settings.PROJECTS_TRASH_RETENTION_DAYS)

    _logger.debug(
        "CODE PLACEHOLDER: **ALL** projects marked as trashed during %s days are deleted",
        retention,
    )
    await asyncio.sleep(5)

    return []


async def update_project(
    app: web.Application,
    *,
    product_name: ProductName,
    user_id: UserID,
    project_id: ProjectID,
    trashed: bool,
):
    # FIXME: can you trash something that is running?

    await projects_api.patch_project(
        app,
        user_id=user_id,
        product_name=product_name,
        project_uuid=project_id,
        project_patch=ProjectPatchExtended(
            trashed_at=arrow.utcnow().datetime if trashed else None
        ),
    )
