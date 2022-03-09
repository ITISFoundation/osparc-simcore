""" Core submodule: dynamic services

"""

import logging
from contextlib import suppress
from typing import Dict

from aiohttp import web
from models_library.projects_state import ProjectStatus
from pydantic.types import PositiveInt
from servicelib.utils import logged_gather

from .. import director_v2_api
from ..users_api import UserRole, get_user_name, get_user_role
from ._core_nodes import is_node_dynamic
from ._core_notify import lock_project_and_notify_state_update
from .projects_utils import extract_dns_without_default_port

log = logging.getLogger(__name__)


async def start_project_dynamic_services(
    request: web.Request, project: Dict, user_id: PositiveInt
) -> None:
    # first get the services if they already exist
    log.debug(
        "getting running interactive services of project %s for user %s",
        f"{project['uuid']=}",
        f"{user_id=}",
    )
    running_services = await director_v2_api.get_dynamic_services(
        request.app, user_id, project["uuid"]
    )
    log.debug(
        "Currently running services %s for user %s",
        f"{running_services=}",
        f"{user_id=}",
    )

    running_service_uuids = [x["service_uuid"] for x in running_services]
    # now start them if needed
    project_needed_services = {
        service_uuid: service
        for service_uuid, service in project["workbench"].items()
        if is_node_dynamic(service["key"]) and service_uuid not in running_service_uuids
    }
    log.debug("Starting services: %s", f"{project_needed_services=}")

    start_service_tasks = [
        director_v2_api.start_dynamic_service(
            request.app,
            user_id=user_id,
            project_id=project["uuid"],
            service_key=service["key"],
            service_version=service["version"],
            service_uuid=service_uuid,
            request_dns=extract_dns_without_default_port(request.url),
            request_scheme=request.headers.get("X-Forwarded-Proto", request.url.scheme),
        )
        for service_uuid, service in project_needed_services.items()
    ]
    results = await logged_gather(*start_service_tasks, reraise=True)
    log.debug("Services start result %s", results)
    for entry in results:
        if entry:
            # if the status is present in the results for the start_service
            # it means that the API call failed
            # also it is enforced that the status is different from 200 OK
            if entry.get("status", 200) != 200:
                log.error("Error while starting dynamic service %s", f"{entry=}")


async def remove_project_dynamic_services(
    user_id: int,
    project_uuid: str,
    app: web.Application,
    notify_users: bool = True,
) -> None:
    """
    raises ProjectNotFoundError
    raises UserNotFoundError
    raises ProjectLockError: project is locked and therefore services cannot be stopped
    """

    log.debug(
        "Removing project interactive services for %s and %s and %s",
        f"{project_uuid=}",
        f"{user_id=}",
        f"{notify_users=}",
    )

    # can raise UserNotFoundError
    user_name_data = await get_user_name(app, user_id)
    user_role: UserRole = await get_user_role(app, user_id)

    #
    # - during the closing process, which might take awhile,
    #   the project is locked so no one opens it at the same time
    # - Users also might get notified
    # - If project is already locked, just ignore
    #
    async with lock_project_and_notify_state_update(
        app,
        project_uuid,
        ProjectStatus.CLOSING,
        user_id,  # required
        user_name_data,
        notify_users=notify_users,
    ):
        with suppress(director_v2_api.DirectorServiceError):
            # FIXME:
            # Here director exceptions are suppressed.
            # In case the service is not found to preserve old behavior
            await director_v2_api.stop_dynamic_services_in_project(
                app=app,
                user_id=user_id,
                project_id=project_uuid,
                save_state=user_role > UserRole.GUEST,
            )
