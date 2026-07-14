import asyncio
import logging
from typing import Protocol

from aiohttp import web
from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.users import UserID
from servicelib.common_headers import UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE
from servicelib.logging_utils import log_context

from ..director_v2 import director_v2_service
from ..storage.api import delete_data_folders_of_project
from . import _projects_repository, _projects_service
from .exceptions import ProjectDeleteError, ProjectNotFoundError

_logger = logging.getLogger(__name__)


class StopServicesCallback(Protocol):
    async def __call__(self, app: web.Application, project_uuid: ProjectID) -> None: ...


async def batch_stop_services_in_project(
    app: web.Application, *, user_id: UserID, project_uuid: ProjectID, product_name: ProductName
) -> None:
    await asyncio.gather(
        director_v2_service.delete_pipeline(app, user_id=user_id, project_id=project_uuid, force=True),
        _projects_service.remove_project_dynamic_services(
            user_id=user_id,
            project_uuid=project_uuid,
            app=app,
            simcore_user_agent=UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE,
            product_name=product_name,
            notify_users=False,
        ),
    )


async def delete_project_as_admin(
    app: web.Application,
    *,
    project_uuid: ProjectID,
    product_name: ProductName,
) -> None:
    try:
        with log_context(_logger, logging.INFO, "hide project"):
            # NOTE: We do not need to use PROJECT_DB_UPDATE_REDIS_LOCK_KEY lock, as hidden field is not passed to frontend
            project = await _projects_repository.patch_project(
                app,
                project_uuid=project_uuid,
                new_partial_project_data={"hidden": True},
            )

        with log_context(_logger, logging.INFO, "stop project"):
            # NOTE: this callback could take long or raise whatever!
            await batch_stop_services_in_project(
                app, user_id=project.prj_owner, project_uuid=project_uuid, product_name=product_name
            )

        with log_context(_logger, logging.INFO, "delete project data"):
            await delete_data_folders_of_project(app, project_uuid, project.prj_owner)

        with log_context(_logger, logging.INFO, "delete project"):
            await _projects_repository.delete_project(app, project_uuid=project_uuid)

    except ProjectNotFoundError as err:
        _logger.debug(
            "Project %s being deleted is already gone. IGNORING error. Details: %s",
            project_uuid,
            err,
        )
    except Exception as err:
        raise ProjectDeleteError(
            project_uuid=project_uuid,
            details=f"Cannot delete project {project_uuid} because of unexpected error. Details: {err}",
        ) from err
