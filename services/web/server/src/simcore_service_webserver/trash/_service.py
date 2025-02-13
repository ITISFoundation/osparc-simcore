import asyncio
import logging
from datetime import timedelta

from aiohttp import web
from models_library.products import ProductName
from models_library.users import UserID

from ..projects import _trash_service
from .settings import get_plugin_settings

_logger = logging.getLogger(__name__)


async def empty_trash(app: web.Application, product_name: ProductName, user_id: UserID):
    assert app  # nosec
    # filter trashed=True and set them to False
    _logger.debug(
        "CODE PLACEHOLDER: all projects marked as trashed of %s in %s are deleted",
        f"{user_id=}",
        f"{product_name=}",
    )

    trashed_projects_ids = await _trash_service.list_trashed_projects(
        app=app, product_name=product_name, user_id=user_id
    )

    for project_id in trashed_projects_ids:
        # TODO: handle error. should not be fail-fast!
        await _trash_service.delete_trashed_project(
            app, user_id=user_id, project_id=project_id
        )


async def prune_trash(app: web.Application) -> list[str]:
    """Deletes expired items in the trash"""
    settings = get_plugin_settings(app)
    retention = timedelta(days=settings.TRASH_RETENTION_DAYS)

    _logger.debug(
        "CODE PLACEHOLDER: **ALL** projects marked as trashed during %s days are deleted",
        retention,
    )
    await asyncio.sleep(5)

    return []
