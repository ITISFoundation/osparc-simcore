import asyncio
import logging
import time
from contextlib import contextmanager
from typing import Any, Protocol

from aiohttp import web
from models_library.projects import ProjectID
from models_library.users import UserID
from servicelib.common_headers import UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE
from servicelib.redis._errors import ProjectLockError

from ..director_v2 import api as director_v2_service
from ..storage import api as storage_service
from ..users.api import FullNameDict
from ..users.exceptions import UserNotFoundError
from . import _access_rights_service, _projects_repository, projects_service
from ._projects_repository_legacy import ProjectDBAPI
from .exceptions import (
    ProjectDeleteError,
    ProjectInvalidRightsError,
    ProjectLockError,
    ProjectNotFoundError,
)

_DELETE_PROJECT_TASK_NAME = (
    "background-task.delete_project/project_uuid={0}.user_id={1}"
)

_logger = logging.getLogger(__name__)


@contextmanager
def _monitor_step(steps: dict[str, Any], *, name: str, elapsed: bool = False):
    # util
    start_time = time.perf_counter()
    steps[name] = {"status": "starting"}
    try:
        yield
    except Exception as exc:
        steps[name]["status"] = "raised"
        steps[name]["exception"] = f"{exc.__class__.__name__}:{exc}"
        raise
    else:
        steps[name]["status"] = "success"
    finally:
        if elapsed:
            steps[name]["elapsed"] = time.perf_counter() - start_time


class StopServicesCallback(Protocol):
    async def __call__(self, app: web.Application, project_uuid: ProjectID) -> None:
        ...


async def batch_stop_services_in_project(
    app: web.Application, *, user_id: UserID, project_uuid: ProjectID
) -> None:
    await asyncio.gather(
        director_v2_service.stop_pipeline(
            app, user_id=user_id, project_id=project_uuid
        ),
        projects_service.remove_project_dynamic_services(
            user_id=user_id,
            project_uuid=f"{project_uuid}",
            app=app,
            simcore_user_agent=UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE,
            notify_users=False,
        ),
    )


async def delete_project_as_admin(
    app: web.Application,
    *,
    project_uuid: ProjectID,
):

    state: dict[str, Any] = {}

    try:
        # 1. hide
        with _monitor_step(state, name="hide"):
            project = await _projects_repository.patch_project(
                app,
                project_uuid=project_uuid,
                new_partial_project_data={"hidden": True},
            )

        # 2. stop
        with _monitor_step(state, name="stop", elapsed=True):
            # NOTE: this callback could take long or raise whatever!
            await batch_stop_services_in_project(
                app, user_id=project.prj_owner, project_uuid=project_uuid
            )

        # 3. delete
        with _monitor_step(state, name="delete"):
            await _projects_repository.delete_project(app, project_uuid=project_uuid)

    except ProjectNotFoundError as err:
        _logger.debug(
            "Project %s being deleted is already gone. IGNORING error. Details: %s",
            project_uuid,
            err,
        )

    except ProjectLockError as err:
        raise ProjectDeleteError(
            project_uuid=project_uuid,
            reason=f"Cannot delete project {project_uuid} because it is currently in use. Details: {err}",
            state=state,
        ) from err

    except Exception as err:
        raise ProjectDeleteError(
            project_uuid=project_uuid,
            reason=f"Unexpected error. Deletion sequence: {state=}",
            state=state,
        ) from err


class RemoveProjectServicesCallable(Protocol):
    # NOTE: this function was tmp added here to avoid refactoring all projects_api in a single PR
    async def __call__(
        self,
        user_id: int,
        project_uuid: str,
        app: web.Application,
        simcore_user_agent: str,
        *,
        notify_users: bool = True,
        user_name: FullNameDict | None = None,
    ) -> None:
        ...


async def mark_project_as_deleted(
    app: web.Application, project_uuid: ProjectID, user_id: UserID
):
    """
    ::raises ProjectInvalidRightsError
    ::raises ProjectNotFoundError
    """
    # NOTE: https://github.com/ITISFoundation/osparc-issues/issues/468
    db: ProjectDBAPI = ProjectDBAPI.get_from_app_context(app)
    product_name = await db.get_project_product(project_uuid=project_uuid)
    await _access_rights_service.check_user_project_permission(
        app,
        project_id=project_uuid,
        user_id=user_id,
        product_name=product_name,
        permission="delete",
    )

    await db.check_project_has_only_one_product(project_uuid)

    # NOTE: if any of the steps below fail, it might results in a
    # services/projects/data that might be incosistent. The GC should
    # be able to detect that and resolve it.
    await db.set_hidden_flag(project_uuid, hidden=True)


async def delete_project(
    app: web.Application,
    project_uuid: ProjectID,
    user_id: UserID,
    simcore_user_agent: str,
    remove_project_dynamic_services: RemoveProjectServicesCallable,
) -> None:
    """Stops dynamic services, deletes data and finally deletes project

    NOTE: this does NOT use fire&forget anymore. This is a decision of the caller to make.

    raises ProjectDeleteError
    """

    _logger.debug(
        "Deleting project '%s' for user '%s' in database",
        f"{project_uuid=}",
        f"{user_id=}",
    )
    db: ProjectDBAPI = ProjectDBAPI.get_from_app_context(app)

    try:
        # NOTE: Project access rights are checked inside this function
        await mark_project_as_deleted(app, project_uuid, user_id)

        # stops dynamic services
        # - raises ProjectNotFoundError, UserNotFoundError, ProjectLockError
        await remove_project_dynamic_services(
            user_id=user_id,
            project_uuid=f"{project_uuid}",
            app=app,
            simcore_user_agent=simcore_user_agent,
            notify_users=False,
        )

        # stops computational services
        # - raises DirectorServiceError
        await director_v2_service.delete_pipeline(app, user_id, project_uuid)

        # rm data from storage
        await storage_service.delete_data_folders_of_project(app, project_uuid, user_id)

        # rm project from database
        await db.delete_project(user_id, f"{project_uuid}")

    except ProjectLockError as err:
        raise ProjectDeleteError(
            project_uuid=project_uuid, reason=f"Project currently in use {err}"
        ) from err

    except (ProjectInvalidRightsError, ProjectNotFoundError, UserNotFoundError) as err:
        raise ProjectDeleteError(
            project_uuid=project_uuid, reason=f"Invalid project state {err}"
        ) from err


def schedule_task(
    app: web.Application,
    project_uuid: ProjectID,
    user_id: UserID,
    simcore_user_agent: str,
    remove_project_dynamic_services: RemoveProjectServicesCallable,
    logger: logging.Logger,
) -> asyncio.Task:
    """Wrap `delete_project` for a `project_uuid` and `user_id` into a Task
        and schedule its execution in the event loop.

    Return the scheduled Task
    """

    def _log_state_when_done(fut: asyncio.Future):
        # the task created in the parent function is typically used
        # to fire&forget therefore this internal function will be used as
        # callback to provide a minimal log that informs about the
        # state of the task when completed.
        try:
            fut.result()
            logger.info(
                "Deleted %s using %s permissions", f"{project_uuid=}", f"{user_id=}"
            )

        except asyncio.exceptions.CancelledError:
            logger.warning(
                "Canceled deletion of %s using %s permissions",
                f"{project_uuid=}",
                f"{user_id=}",
            )
            raise

        except ProjectDeleteError:
            logger.exception(
                "Failed to delete %s using %s permissions",
                f"{project_uuid=}",
                f"{user_id=}",
            )

        except ProjectInvalidRightsError:
            logger.exception(
                "%s does not have permission to delete %s",
                f"{user_id=}",
                f"{project_uuid=}",
            )

        except Exception:  # pylint: disable=broad-except
            logger.exception(
                "Unexpected error while deleting %s with %spermissions",
                f"{project_uuid=}",
                f"{user_id=}",
            )

    # ------

    task = asyncio.create_task(
        delete_project(
            app,
            project_uuid,
            user_id,
            simcore_user_agent,
            remove_project_dynamic_services,
        ),
        name=_DELETE_PROJECT_TASK_NAME.format(project_uuid, user_id),
    )

    assert task.get_name() == _DELETE_PROJECT_TASK_NAME.format(  # nosec
        project_uuid, user_id
    )

    task.add_done_callback(_log_state_when_done)
    return task


def get_scheduled_tasks(project_uuid: ProjectID, user_id: UserID) -> list[asyncio.Task]:
    """Returns tasks matching delete-project task's name."""
    return [
        task
        for task in asyncio.all_tasks()
        if task.get_name() == _DELETE_PROJECT_TASK_NAME.format(project_uuid, user_id)
    ]
