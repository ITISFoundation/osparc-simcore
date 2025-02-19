# NOTE: should replace _crud_api_delete.py:delete_project

import logging
from typing import Protocol

from aiohttp import web
from models_library.projects import ProjectID
from servicelib.redis._errors import ProjectLockError
from simcore_service_director_v2.core.errors import ProjectNotFoundError
from simcore_service_webserver.projects.exceptions import ProjectDeleteError

from . import _projects_db as _projects_repository

_logger = logging.getLogger(__name__)


class StopServicesCallback(Protocol):
    async def __call__(self, app: web.Application, project_uuid: ProjectID) -> None:
        ...


async def delete_project_as_admin(
    app: web.Application,
    *,
    project_uuid: ProjectID,
    stop_project_services_as_admin: StopServicesCallback | None,
):
    hidden = False
    stopped = not stop_project_services_as_admin
    deleted = False

    try:
        # hide
        await _projects_repository.patch_project(
            app,
            project_uuid=project_uuid,
            new_partial_project_data={"hidden": True},
        )
        hidden = True

        if stop_project_services_as_admin:
            # NOTE: this callback could take long or raise whatever!
            await stop_project_services_as_admin(app, project_uuid)
            stopped = True

        await _projects_repository.delete_project(app, project_uuid=project_uuid)
        deleted = True

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
        ) from err

    except Exception as err:
        raise ProjectDeleteError(
            project_uuid=project_uuid,
            reason=f"Unexpected error. Deletion sequence: {hidden=}, {stopped=}, {deleted=} ",
        ) from err
