import asyncio
import logging

import arrow
from aiohttp import web
from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.users import UserID
from servicelib.aiohttp.application_keys import APP_FIRE_AND_FORGET_TASKS_KEY
from servicelib.common_headers import UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE
from servicelib.utils import fire_and_forget_task

from ..director_v2 import api as director_v2_api
from ..dynamic_scheduler import api as dynamic_scheduler_api
from . import projects_service
from ._access_rights_api import check_user_project_permission
from .exceptions import ProjectRunningConflictError
from .models import ProjectPatchInternalExtended

_logger = logging.getLogger(__name__)


async def _is_project_running(
    app: web.Application,
    *,
    user_id: UserID,
    project_id: ProjectID,
) -> bool:
    return bool(
        await director_v2_api.is_pipeline_running(
            app, user_id=user_id, project_id=project_id
        )
    ) or bool(
        await dynamic_scheduler_api.list_dynamic_services(
            app, user_id=user_id, project_id=project_id
        )
    )


async def trash_project(
    app: web.Application,
    *,
    product_name: ProductName,
    user_id: UserID,
    project_id: ProjectID,
    force_stop_first: bool,
    explicit: bool,
):
    """

    Raises:
        ProjectStopError:
        ProjectRunningConflictError:
    """
    await check_user_project_permission(
        app,
        project_id=project_id,
        user_id=user_id,
        product_name=product_name,
        permission="write",
    )

    if force_stop_first:

        async def _schedule():
            await asyncio.gather(
                director_v2_api.stop_pipeline(
                    app, user_id=user_id, project_id=project_id
                ),
                projects_service.remove_project_dynamic_services(
                    user_id=user_id,
                    project_uuid=f"{project_id}",
                    app=app,
                    simcore_user_agent=UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE,
                    notify_users=False,
                ),
            )

        fire_and_forget_task(
            _schedule(),
            task_suffix_name=f"trash_project_force_stop_first_{user_id=}_{project_id=}",
            fire_and_forget_tasks_collection=app[APP_FIRE_AND_FORGET_TASKS_KEY],
        )

    elif await _is_project_running(app, user_id=user_id, project_id=project_id):
        raise ProjectRunningConflictError(
            project_uuid=project_id,
            user_id=user_id,
            product_name=product_name,
        )

    await projects_service.patch_project(
        app,
        user_id=user_id,
        product_name=product_name,
        project_uuid=project_id,
        project_patch=ProjectPatchInternalExtended(
            trashed_at=arrow.utcnow().datetime,
            trashed_explicitly=explicit,
            trashed_by=user_id,
        ),
    )


async def untrash_project(
    app: web.Application,
    *,
    product_name: ProductName,
    user_id: UserID,
    project_id: ProjectID,
):
    # NOTE: check_user_project_permission is inside projects_api.patch_project
    await projects_service.patch_project(
        app,
        user_id=user_id,
        product_name=product_name,
        project_uuid=project_id,
        project_patch=ProjectPatchInternalExtended(
            trashed_at=None, trashed_explicitly=False, trashed_by=None
        ),
    )
