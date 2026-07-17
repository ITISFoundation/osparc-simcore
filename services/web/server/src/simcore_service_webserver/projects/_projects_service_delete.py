import asyncio
import datetime
import logging
from typing import Final

from aiohttp import web
from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.users import UserID
from servicelib.aiohttp import status
from servicelib.common_headers import UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE
from servicelib.exception_utils import suppress_exceptions
from servicelib.logging_utils import log_context
from tenacity import before_sleep_log, retry, retry_if_result, stop_after_delay, wait_fixed

from ..director_v2 import director_v2_service
from ..director_v2.exceptions import DirectorV2ServiceError
from ..storage import api as storage_service
from . import _projects_repository, _projects_service
from .exceptions import ProjectDeleteError, ProjectNotFoundError

_logger = logging.getLogger(__name__)


async def batch_stop_services_in_project(
    app: web.Application, *, user_id: UserID, project_uuid: ProjectID, product_name: ProductName
) -> None:
    await asyncio.gather(
        director_v2_service.stop_pipeline(app, user_id=user_id, project_id=project_uuid),
        _projects_service.remove_project_dynamic_services(
            user_id=user_id,
            project_uuid=project_uuid,
            app=app,
            simcore_user_agent=UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE,
            product_name=product_name,
            notify_users=False,
        ),
    )


_STOP_PIPELINE_MAX_WAIT_TIME: Final[datetime.timedelta] = datetime.timedelta(seconds=60)


@retry(
    retry=retry_if_result(lambda result: result is False),
    reraise=True,
    stop=stop_after_delay(_STOP_PIPELINE_MAX_WAIT_TIME),
    wait=wait_fixed(1),
    before_sleep=before_sleep_log(_logger, logging.INFO),
)
async def _wait_for_pipeline_to_stop(app: web.Application, *, user_id: UserID, project_uuid: ProjectID) -> bool:
    return await director_v2_service.is_pipeline_running(app, user_id=user_id, project_id=project_uuid) is False


def _skip_if_pipeline_not_found(exception: BaseException) -> bool:
    assert isinstance(exception, DirectorV2ServiceError)  # nosec
    return exception.status == status.HTTP_404_NOT_FOUND


@suppress_exceptions(
    (DirectorV2ServiceError,),
    reason="Pipeline not found or already stopped or partially deleted",
    predicate=_skip_if_pipeline_not_found,
)
async def _stop_and_wait_for_pipeline_to_stop(
    app: web.Application, *, user_id: UserID, project_uuid: ProjectID
) -> None:
    await director_v2_service.stop_pipeline(app, user_id=user_id, project_id=project_uuid)
    await _wait_for_pipeline_to_stop(app, user_id=user_id, project_uuid=project_uuid)


async def delete_project_as_admin(
    app: web.Application,
    *,
    project_uuid: ProjectID,
    product_name: ProductName,
) -> None:
    """Deletes a project and all its data, including the pipeline and dynamic services.
        This call is idempotent and may be called multiple times without raising an error
        if the project is already deleted.
        It can be called multiple times in case ProjectDeleteError is raised until the project is fully deleted.
        if a computational pipeline is running, it will be stopped first and waited for it to stop
        before deleting the project.
    Raises:
        ProjectDeleteError: if the project could not be deleted
    """
    try:
        with log_context(_logger, logging.INFO, "hide project"):
            # NOTE: We do not need to use PROJECT_DB_UPDATE_REDIS_LOCK_KEY lock, as hidden field is not passed to frontend
            project = await _projects_repository.patch_project(
                app,
                project_uuid=project_uuid,
                new_partial_project_data={"hidden": True},
            )

        with log_context(_logger, logging.INFO, "stop project services"):
            asyncio.gather(
                _stop_and_wait_for_pipeline_to_stop(app, user_id=project.prj_owner, project_uuid=project_uuid),
                _projects_service.remove_project_dynamic_services(
                    user_id=project.prj_owner,
                    project_uuid=project_uuid,
                    app=app,
                    simcore_user_agent=UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE,
                    product_name=product_name,
                    notify_users=False,
                ),
            )

        with log_context(_logger, logging.INFO, "delete project data"):
            # NOTE: this is required as comp_pipelines/comp_tasks are not using Foreign keys and are not deleted automatically when the project is deleted
            await director_v2_service.delete_pipeline(app, user_id=project.prj_owner, project_id=project_uuid)

            await storage_service.delete_project_data_folders(
                app, product_name=product_name, user_id=project.prj_owner, project_id=project_uuid
            )

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
