import logging
from typing import Final

from aiohttp import web
from common_library.users_enums import UserRole
from models_library.api_schemas_directorv2.dynamic_services import DynamicServiceGet
from models_library.api_schemas_dynamic_scheduler.dynamic_services import (
    DynamicServiceStop,
)
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from servicelib.common_headers import UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE
from servicelib.logging_errors import create_troubleshootting_log_kwargs
from servicelib.logging_utils import log_catch, log_context
from servicelib.utils import limited_as_completed, limited_gather

from ..dynamic_scheduler import api as dynamic_scheduler_service
from ..projects._projects_service import (
    is_node_id_present_in_any_project_workbench,
    list_node_ids_in_project,
)
from ..projects.api import has_user_project_access_rights
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

    with log_catch(_logger, reraise=False), log_context(
        _logger,
        logging.INFO,
        f"removing {(service.node_uuid, service.host)} with {save_service_state=}",
    ):
        await dynamic_scheduler_service.stop_dynamic_service(
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

    running_services = await dynamic_scheduler_service.list_dynamic_services(app)
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

    # NOTE: Always skip orphan repmoval when `list_node_ids_in_project` raises an error.
    # Why? If a service is running but the nodes form the correspondign project cannot be listed,
    # the service will be considered as orphaned and closed.
    potentially_running_service_ids: list[set[NodeID]] = []
    async for project_nodes_future in limited_as_completed(
        (
            list_node_ids_in_project(app, project_id)
            for project_id in known_opened_project_ids
        ),
        limit=_MAX_CONCURRENT_CALLS,
    ):
        try:
            project_nodes = await project_nodes_future
            potentially_running_service_ids.append(project_nodes)
        except BaseException as e:  # pylint:disable=broad-exception-caught
            _logger.warning(
                create_troubleshootting_log_kwargs(
                    (
                        "Skipping orpahn services removal, call to "
                        "`list_node_ids_in_project` raised"
                    ),
                    error=e,
                    error_context={
                        "running_services": running_services,
                        "running_services_by_id": running_services_by_id,
                        "known_opened_project_ids": known_opened_project_ids,
                    },
                ),
                exc_info=True,
            )
            continue

    potentially_running_service_ids_set: set[NodeID] = set().union(
        *(node_id for node_id in potentially_running_service_ids)
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
    await limited_gather(
        *(
            _remove_service(app, node_id, running_services_by_id[node_id])
            for node_id in orphaned_running_service_ids
        ),
        log=_logger,
        limit=_MAX_CONCURRENT_CALLS,
    )
