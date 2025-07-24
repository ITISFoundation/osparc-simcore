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

from ..director_v2 import director_v2_service
from . import _projects_repository, _projects_service
from .exceptions import ProjectDeleteError, ProjectNotFoundError

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
    async def __call__(self, app: web.Application, project_uuid: ProjectID) -> None: ...


async def batch_stop_services_in_project(
    app: web.Application, *, user_id: UserID, project_uuid: ProjectID
) -> None:
    await asyncio.gather(
        director_v2_service.stop_pipeline(
            app, user_id=user_id, project_id=project_uuid
        ),
        _projects_service.remove_project_dynamic_services(
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
            # NOTE: We do not need to use PROJECT_DB_UPDATE_REDIS_LOCK_KEY lock, as hidden field is not passed to frontend
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
