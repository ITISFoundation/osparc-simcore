import contextlib
import logging
from typing import Any

from aiohttp import web
from servicelib.common_headers import UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE
from servicelib.logging_utils import log_decorator
from servicelib.utils import logged_gather
from simcore_postgres_database.models.users import UserRole

from ..director_v2 import api
from ..director_v2.exceptions import (
    DirectorServiceError,
    ServiceWaitingForManualIntervention,
)
from ..projects.db import ProjectDBAPI
from ..projects.projects_api import (
    get_workbench_node_ids_from_project_uuid,
    is_node_id_present_in_any_project_workbench,
)
from ..resource_manager.registry import RedisResourceRegistry
from ..users.api import get_user_role
from ..users.exceptions import UserNotFoundError

_logger = logging.getLogger(__name__)


@log_decorator(_logger, log_traceback=True)
async def _remove_single_service_if_orphan(
    app: web.Application,
    dynamic_service: dict[str, Any],
    currently_opened_projects_node_ids: dict[str, str],
) -> None:
    """
    Removes the service if it is an orphan. Otherwise the service is left running.
    """

    service_host = dynamic_service["service_host"]
    # if not present in DB or not part of currently opened projects, can be removed
    service_uuid = dynamic_service["service_uuid"]
    # if the node does not exist in any project in the db
    # they can be safely remove it without saving any state
    if not await is_node_id_present_in_any_project_workbench(app, service_uuid):
        _logger.info(
            "Will remove orphaned service without saving state since "
            "this service is not part of any project %s",
            f"{service_host=}",
        )
        try:
            await api.stop_dynamic_service(
                app,
                service_uuid,
                simcore_user_agent=UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE,
                save_state=False,
            )
        except DirectorServiceError as err:
            _logger.warning("Error while stopping service: %s", err)
        return

    # if the node is not present in any of the currently opened project it shall be closed
    if service_uuid not in currently_opened_projects_node_ids:
        if service_state := dynamic_service.get("service_state") in [
            "pulling",
            "starting",
        ]:
            # Services returned in running_interactive_services
            # might be still pulling its image and when stop_service is
            # called, will cancel the pull operation as well.
            # This enforces next run to start again by pulling the image
            # which is costly and sometimes the cause of timeout and
            # service malfunction.
            # For that reason, we prefer here to allow the image to
            # be completely pulled and stop it instead at the next gc round
            #
            # This should eventually be responsibility of the director, but
            # the functionality is in the old service which is frozen.
            #
            # a service state might be one of [pending, pulling, starting, running, complete, failed]
            _logger.warning(
                "Skipping %s since service state is %s",
                f"{service_host=}",
                service_state,
            )
            return

        _logger.info("Will remove service %s", service_host)
        try:
            # let's be conservative here.
            # 1. opened project disappeared from redis?
            # 2. something bad happened when closing a project?

            user_id = int(dynamic_service.get("user_id", -1))

            user_role: UserRole | None = None
            try:
                user_role = await get_user_role(app, user_id)
            except (UserNotFoundError, ValueError):
                user_role = None

            project_uuid = dynamic_service["project_id"]

            save_state = await ProjectDBAPI.get_from_app_context(app).has_permission(
                user_id, project_uuid, "write"
            )
            if user_role is None or user_role <= UserRole.GUEST:
                save_state = False
            # -------------------------------------------

            with contextlib.suppress(ServiceWaitingForManualIntervention):
                await api.stop_dynamic_service(
                    app,
                    service_uuid,
                    UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE,
                    save_state,
                )

        except DirectorServiceError as err:
            _logger.warning("Error while stopping service: %s", err)


async def remove_orphaned_services(
    registry: RedisResourceRegistry, app: web.Application
) -> None:
    """Removes orphan services: which are no longer tracked in the database

    Multiple deployments can be active at the same time on the same cluster.
    This will also check the current SWARM_STACK_NAME label of the service which
    must be matching its own. The director service spawns dynamic services
    which have this new label and it also filters by this label.

    If the service is a dynamic service
    """
    _logger.debug("Starting orphaned services removal...")

    currently_opened_projects_node_ids: dict[str, str] = {}
    alive_keys, _ = await registry.get_all_resource_keys()
    for alive_key in alive_keys:
        resources = await registry.get_resources(alive_key)
        if "project_id" not in resources:
            continue

        project_uuid = resources["project_id"]
        node_ids: set[str] = await get_workbench_node_ids_from_project_uuid(
            app, project_uuid
        )
        for node_id in node_ids:
            currently_opened_projects_node_ids[node_id] = project_uuid

    running_dynamic_services: list[dict[str, Any]] = []
    try:
        running_dynamic_services = await api.list_dynamic_services(app)
    except api.DirectorServiceError:
        _logger.debug("Could not fetch running_interactive_services")

    _logger.info(
        "Currently running services %s",
        [
            (x.get("service_uuid", ""), x.get("service_host", ""))
            for x in running_dynamic_services
        ],
    )

    # if there are multiple dynamic services to stop,
    # this ensures they are being stopped in parallel
    # when the user is timed out and the GC needs to close
    # a big study with logs of heavy projects, this will
    # ensure it gets done in parallel
    tasks = [
        _remove_single_service_if_orphan(
            app, service, currently_opened_projects_node_ids
        )
        for service in running_dynamic_services
    ]
    await logged_gather(*tasks, reraise=False)

    _logger.debug("Finished orphaned services removal")
