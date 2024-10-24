import asyncio
import logging
from datetime import timedelta

import arrow
from aiohttp import web
from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.users import UserID
from servicelib.common_headers import UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE
from simcore_service_webserver.director_v2.exceptions import DirectorServiceError

from ..director_v2 import api as director_v2_api
from . import projects_api
from .exceptions import ProjectLockError, ProjectRunningConflictError, ProjectStopError
from .models import ProjectPatchExtended
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


async def trash_project(
    app: web.Application,
    *,
    product_name: ProductName,
    user_id: UserID,
    project_id: ProjectID,
    trashed: bool,
    forced: bool = True,
):
    if trashed:
        # stop first

        if forced:
            try:
                await projects_api.remove_project_dynamic_services(
                    user_id=user_id,
                    project_uuid=f"{project_id}",
                    app=app,
                    simcore_user_agent=UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE,
                    notify_users=False,
                )

                await director_v2_api.delete_pipeline(
                    app, user_id=user_id, project_id=project_id
                )
            except (DirectorServiceError, ProjectLockError) as exc:
                raise ProjectStopError(
                    project_uuid=project_id,
                    user_id=user_id,
                    product_name=product_name,
                    from_err=exc,
                ) from exc
        else:

            running = await director_v2_api.is_pipeline_running(
                app=app, user_id=user_id, project_id=project_id
            )
            # NOTE: must do here as well for dynamic services but needs refactoring!
            if running:
                raise ProjectRunningConflictError(
                    project_uuid=project_id,
                    user_id=user_id,
                    product_name=product_name,
                )

    # mark as trash
    await projects_api.patch_project(
        app,
        user_id=user_id,
        product_name=product_name,
        project_uuid=project_id,
        project_patch=ProjectPatchExtended(
            trashed_at=arrow.utcnow().datetime if trashed else None
        ),
    )
