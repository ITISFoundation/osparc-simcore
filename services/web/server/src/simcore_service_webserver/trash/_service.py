import logging
from datetime import timedelta
from typing import Final

import arrow
from aiohttp import web
from models_library.products import ProductName
from models_library.users import UserID
from servicelib.logging_errors import create_troubleshotting_log_kwargs
from servicelib.logging_utils import log_context
from simcore_service_webserver.products import _service as products_service

from ..folders import folders_trash_service
from ..projects import projects_trash_service
from .settings import get_plugin_settings

_logger = logging.getLogger(__name__)

_TIP: Final[str] = (
    "`empty_trash_safe` is set `fail_fast=False`."
    "\nErrors while deletion are ignored."
    "\nNew runs might resolve them"
)


async def _empty_explicitly_trashed_projects(
    app: web.Application, product_name: ProductName, user_id: UserID
):
    trashed_projects_ids = (
        await projects_trash_service.list_explicitly_trashed_projects(
            app=app, product_name=product_name, user_id=user_id
        )
    )

    with log_context(
        _logger,
        logging.DEBUG,
        "Deleting %s explicitly trashed projects",
        len(trashed_projects_ids),
    ):
        for project_id in trashed_projects_ids:
            try:

                await projects_trash_service.delete_explicitly_trashed_project(
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
                        tip=_TIP,
                    )
                )


async def _empty_explicitly_trashed_folders_and_content(
    app: web.Application, product_name: ProductName, user_id: UserID
):
    trashed_folders_ids = await folders_trash_service.list_explicitly_trashed_folders(
        app=app, product_name=product_name, user_id=user_id
    )

    with log_context(
        _logger,
        logging.DEBUG,
        "Deleting %s trashed folders (and all its content)",
        len(trashed_folders_ids),
    ):
        for folder_id in trashed_folders_ids:
            try:
                await folders_trash_service.delete_trashed_folder(
                    app,
                    product_name=product_name,
                    user_id=user_id,
                    folder_id=folder_id,
                )

            except Exception as exc:  # pylint: disable=broad-exception-caught
                _logger.warning(
                    **create_troubleshotting_log_kwargs(
                        "Error deleting a trashed folders (and content) while emptying trash.",
                        error=exc,
                        error_context={
                            "folder_id": folder_id,
                            "product_name": product_name,
                            "user_id": user_id,
                        },
                        tip=_TIP,
                    )
                )


async def safe_empty_trash(
    app: web.Application, *, product_name: ProductName, user_id: UserID
):
    await _empty_explicitly_trashed_projects(app, product_name, user_id)

    await _empty_explicitly_trashed_folders_and_content(app, product_name, user_id)


async def safe_delete_expired_trash_as_admin(app: web.Application) -> None:
    settings = get_plugin_settings(app)
    retention = timedelta(days=settings.TRASH_RETENTION_DAYS)
    delete_until = arrow.now().datetime - retention

    app_products_names = await products_service.list_products_names(app)

    for product_name in app_products_names:

        ctx = {
            "delete_until": delete_until,
            "retention": retention,
            "product_name": product_name,
        }

        with log_context(
            _logger,
            logging.DEBUG,
            "Deleting items marked as trashed before %s in %s [trashed_at < %s will be deleted]",
            retention,
            product_name,
            delete_until,
        ):
            try:

                await folders_trash_service.batch_delete_trashed_folders_as_admin(
                    app,
                    trashed_before=delete_until,
                    product_name=product_name,
                    fail_fast=False,
                )

            except Exception as exc:  # pylint: disable=broad-exception-caught
                _logger.warning(
                    **create_troubleshotting_log_kwargs(
                        "Error batch deleting expired trashed folders as admin.",
                        error=exc,
                        error_context=ctx,
                    )
                )

            try:

                deleted_project_ids = (
                    await projects_trash_service.batch_delete_trashed_projects_as_admin(
                        app,
                        trashed_before=delete_until,
                        fail_fast=False,
                    )
                )

                _logger.info("Deleted %d trashed projects", len(deleted_project_ids))

            except Exception as exc:  # pylint: disable=broad-exception-caught
                _logger.warning(
                    **create_troubleshotting_log_kwargs(
                        "Error batch deleting expired projects as admin.",
                        error=exc,
                        error_context=ctx,
                    )
                )
