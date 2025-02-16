import asyncio
import logging
from datetime import timedelta

import arrow
from aiohttp import web
from models_library.products import ProductName
from models_library.users import UserID
from servicelib.logging_errors import create_troubleshotting_log_kwargs
from servicelib.logging_utils import log_context

from ..projects import _trash_service
from .settings import get_plugin_settings

_logger = logging.getLogger(__name__)


async def empty_trash_safe(
    app: web.Application, product_name: ProductName, user_id: UserID
):
    assert app  # nosec

    trashed_projects_ids = await _trash_service.list_trashed_projects(
        app=app, product_name=product_name, user_id=user_id
    )

    with log_context(
        _logger,
        logging.DEBUG,
        "Deleting %s trashed projects",
        len(trashed_projects_ids),
    ):
        for project_id in trashed_projects_ids:
            try:

                await _trash_service.delete_trashed_project(
                    app,
                    user_id=user_id,
                    project_id=project_id,
                )

            except Exception as exc:  # pylint: disable=broad-exception-caught
                _logger.warning(
                    **create_troubleshotting_log_kwargs(
                        "Error deleting a trashed project while emptying trash.",
                        error=exc,
                        error_context={
                            "project_id": project_id,
                            "product_name": product_name,
                            "user_id": user_id,
                        },
                        tip="`empty_trash_safe` is set `fail_fast=False`."
                        "\nErrors while deletion are ignored."
                        "\nNew runs might resolve them",
                    )
                )


async def prune_trash(app: web.Application) -> list[str]:
    """Deletes expired items in the trash"""
    settings = get_plugin_settings(app)

    # app-wide
    retention = timedelta(days=settings.TRASH_RETENTION_DAYS)
    expiration_dt = arrow.now().datetime - retention

    # TODO:
    #   for each product
    #      list_trashed_projects
    #      sort by owner
    #      as owner start deleting
    _logger.debug(
        "CODE PLACEHOLDER: **ALL** items marked as trashed during %s days are deleted (those marked before %s)",
        retention,
        expiration_dt,
    )
    await asyncio.sleep(5)

    return []
