import asyncio
import logging
from datetime import timedelta
from typing import Final

import arrow
from aiohttp import web
from models_library.products import ProductName
from models_library.users import UserID
from servicelib.logging_errors import create_troubleshootting_log_kwargs
from servicelib.logging_utils import log_context

from ..folders import folders_trash_service
from ..products import products_service
from ..projects import projects_trash_service
from ..workspaces import workspaces_trash_service
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
                    **create_troubleshootting_log_kwargs(
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
                    **create_troubleshootting_log_kwargs(
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


async def _empty_explicitely_trashed_workspaces_and_content(
    app: web.Application, product_name: ProductName, user_id: UserID
):
    trashed_workspaces_ids = await workspaces_trash_service.list_trashed_workspaces(
        app=app, product_name=product_name, user_id=user_id
    )

    with log_context(
        _logger,
        logging.DEBUG,
        "Deleting %s trashed workspaces (and all its content)",
        len(trashed_workspaces_ids),
    ):
        for workspace_id in trashed_workspaces_ids:
            try:
                await workspaces_trash_service.delete_trashed_workspace(
                    app,
                    product_name=product_name,
                    user_id=user_id,
                    workspace_id=workspace_id,
                )

            except Exception as exc:  # pylint: disable=broad-exception-caught
                _logger.warning(
                    **create_troubleshootting_log_kwargs(
                        "Error deleting a trashed workspace (and content) while emptying trash.",
                        error=exc,
                        error_context={
                            "workspace_id": workspace_id,
                            "product_name": product_name,
                            "user_id": user_id,
                        },
                        tip=_TIP,
                    )
                )


async def safe_empty_trash(
    app: web.Application,
    *,
    product_name: ProductName,
    user_id: UserID,
    on_explicitly_trashed_projects_deleted: asyncio.Event | None = None,
):
    # Delete explicitly trashed projects & notify
    await _empty_explicitly_trashed_projects(app, product_name, user_id)
    if on_explicitly_trashed_projects_deleted:
        on_explicitly_trashed_projects_deleted.set()

    # Delete explicitly trashed folders (and all implicitly trashed sub-folders and projects)
    await _empty_explicitly_trashed_folders_and_content(app, product_name, user_id)

    # Delete explicitly trashed workspaces (and all implicitly trashed sub-folders and projects)
    await _empty_explicitely_trashed_workspaces_and_content(app, product_name, user_id)


async def safe_delete_expired_trash_as_admin(app: web.Application) -> None:
    settings = get_plugin_settings(app)
    retention = timedelta(days=settings.TRASH_RETENTION_DAYS)
    delete_until = arrow.now().datetime - retention

    app_products_names = await products_service.list_products_names(app)

    with log_context(
        _logger,
        logging.DEBUG,
        "Deleting items marked as trashed before %s [trashed_at < %s will be deleted]",
        retention,
        delete_until,
    ):
        ctx = {
            "delete_until": delete_until,
            "retention": retention,
        }

        try:
            deleted_workspace_ids = (
                await workspaces_trash_service.batch_delete_trashed_workspaces_as_admin(
                    app,
                    trashed_before=delete_until,
                    fail_fast=False,
                )
            )
            _logger.info("Deleted %d trashed workspaces", len(deleted_workspace_ids))

        except Exception as exc:  # pylint: disable=broad-exception-caught
            _logger.exception(
                **create_troubleshootting_log_kwargs(
                    "Unexpected error while batch deleting expired workspaces as admin:",
                    error=exc,
                    error_context=ctx,
                )
            )

        for product_name in app_products_names:
            try:
                await folders_trash_service.batch_delete_trashed_folders_as_admin(
                    app,
                    trashed_before=delete_until,
                    product_name=product_name,
                    fail_fast=False,
                )

            except Exception as exc:  # pylint: disable=broad-exception-caught
                ctx_with_product = {**ctx, "product_name": product_name}
                _logger.exception(
                    **create_troubleshootting_log_kwargs(
                        "Unexpected error while batch deleting expired trashed folders as admin:",
                        error=exc,
                        error_context=ctx_with_product,
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
            _logger.exception(
                **create_troubleshootting_log_kwargs(
                    "Unexpected error while batch deleting expired projects as admin:",
                    error=exc,
                    error_context=ctx,
                )
            )
