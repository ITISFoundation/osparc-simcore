import logging
from typing import Final

from aiohttp import web
from models_library.api_schemas_directorv2.dynamic_services import DynamicServiceGet
from models_library.api_schemas_dynamic_scheduler.dynamic_services import (
    DynamicServiceStop,
)
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from servicelib.common_headers import UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE
from servicelib.logging_utils import log_catch, log_context
from servicelib.utils import logged_gather
from simcore_postgres_database.models.users import UserRole

from ..dynamic_scheduler import api as dynamic_scheduler_api
from ..projects.api import has_user_project_access_rights
from ..projects.projects_service import (
    is_node_id_present_in_any_project_workbench,
    list_node_ids_in_project,
)
from ..resource_manager.registry import RedisResourceRegistry
from ..users.api import get_user_role
from ..users.exceptions import UserNotFoundError

_logger = logging.getLogger(__name__)

_MAX_CONCURRENT_CALLS: Final[int] = 2


async def _remove_service(
    app: web.Application, node_id: NodeID, service: DynamicServiceGet
) -> None:
    save_service_state = True
    if not await is_node_id_present_in_any_project_workbench(app, node_id):
        # this is a loner service that is not part of any project
        save_service_state = False
    else:
        try:
            if await get_user_role(app, user_id=service.user_id) <= UserRole.GUEST:
                save_service_state = False
            else:
                save_service_state = await has_user_project_access_rights(
                    app,
                    project_id=service.project_id,
                    user_id=service.user_id,
                    permission="write",
                )
        except (UserNotFoundError, ValueError):
            save_service_state = False

    with log_context(
        _logger,
        logging.INFO,
        msg=f"removing {(service.node_uuid, service.host)} with {save_service_state=}",
    ):
        await dynamic_scheduler_api.stop_dynamic_service(
            app,
            dynamic_service_stop=DynamicServiceStop(
                user_id=service.user_id,
                project_id=service.project_id,
                node_id=service.node_uuid,
                simcore_user_agent=UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE,
                save_state=save_service_state,
            ),
        )


async def _list_opened_project_ids(registry: RedisResourceRegistry) -> list[ProjectID]:
    opened_projects: list[ProjectID] = []
    all_session_alive, _ = await registry.get_all_resource_keys()
    for alive_session in all_session_alive:
        resources = await registry.get_resources(alive_session)
        if "project_id" in resources:
            opened_projects.append(ProjectID(resources["project_id"]))
    return opened_projects


async def remove_orphaned_services(
    registry: RedisResourceRegistry, app: web.Application
) -> None:
    """Removes orphan services: orphan services are dynamic services running in the cluster
    that are not known to the webserver (i.e. which service UUID is not part of any node inside opened projects).

    """

    # NOTE: First get the runnning services in the system before checking what should be opened
    # otherwise if some time goes it could very well be that there are new projects opened
    # in between and the GC would remove services that actually should be running.

    with log_catch(_logger, reraise=False):
        running_services = await dynamic_scheduler_api.list_dynamic_services(app)
        if not running_services:
            # nothing to do
            return
        _logger.debug(
            "Actual running dynamic services: %s",
            [(x.node_uuid, x.host) for x in running_services],
        )
        running_services_by_id: dict[NodeID, DynamicServiceGet] = {
            service.node_uuid: service for service in running_services
        }

        known_opened_project_ids = await _list_opened_project_ids(registry)
        potentially_running_service_ids: list[
            set[NodeID] | BaseException
        ] = await logged_gather(
            *(list_node_ids_in_project(app, _) for _ in known_opened_project_ids),
            log=_logger,
            max_concurrency=_MAX_CONCURRENT_CALLS,
            reraise=False,
        )
        potentially_running_service_ids_set: set[NodeID] = set().union(
            *(_ for _ in potentially_running_service_ids if isinstance(_, set))
        )
        _logger.debug(
            "Allowed service UUIDs from known opened projects: %s",
            potentially_running_service_ids_set,
        )

        # compute the difference to find the orphaned services
        orphaned_running_service_ids = (
            set(running_services_by_id) - potentially_running_service_ids_set
        )
        _logger.debug("Found orphaned services: %s", orphaned_running_service_ids)
        # NOTE: no need to not reraise here, since we catch everything above
        # and logged_gather first runs everything
        await logged_gather(
            *(
                _remove_service(app, node_id, running_services_by_id[node_id])
                for node_id in orphaned_running_service_ids
            ),
            log=_logger,
            max_concurrency=_MAX_CONCURRENT_CALLS,
        )
