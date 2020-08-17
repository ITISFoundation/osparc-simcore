"""The garbage collector runs as an aiohttp background task at pre-defined interval until the aiohttp app is closed.

    Its tasks are to collect resources that are no longer "alive".
    The tasks are defined as alive when the registry alive key is no longer available (see (registry.py)),
    thus the corresponding key is deamed as dead, and so are its attached resources if any.
    The garbage collector shall then close/delete these resources.
"""

import asyncio
import logging
from itertools import chain
from typing import Dict, List

from aiohttp import web

from servicelib.observer import emit
from servicelib.utils import logged_gather
from simcore_service_webserver.director.director_api import (
    get_running_interactive_services,
    stop_service,
)
from simcore_service_webserver.director.director_exceptions import (
    DirectorException,
    ServiceNotFoundError,
)
from simcore_service_webserver.projects.projects_api import (
    delete_project_from_db,
    get_workbench_node_ids_from_project_uuid,
    is_node_id_present_in_any_project_workbench,
)
from simcore_service_webserver.projects.projects_db import APP_PROJECT_DBAPI
from simcore_service_webserver.projects.projects_exceptions import ProjectNotFoundError
from simcore_service_webserver.users_api import (
    delete_user,
    get_guest_user_ids,
    is_user_guest,
)

from .config import APP_GARBAGE_COLLECTOR_KEY, get_garbage_collector_interval
from .registry import RedisResourceRegistry, get_registry

logger = logging.getLogger(__name__)


async def collect_garbage(registry: RedisResourceRegistry, app: web.Application):
    logger.info("collecting garbage...")
    alive_keys, dead_keys = await registry.get_all_resource_keys()
    logger.debug("potential dead keys: %s", dead_keys)

    # check if we find potential stuff to close
    for dead_key in dead_keys:
        dead_resources = await registry.get_resources(dead_key)
        if not dead_resources:
            # no resource, remove the key then
            await registry.remove_key(dead_key)
            continue
        logger.debug("found the following resources: %s", dead_resources)
        # find if there are alive entries using these resources
        for resource_name, resource_value in dead_resources.items():
            other_keys = [
                x
                for x in await registry.find_keys((resource_name, resource_value))
                if x != dead_key
            ]
            # the resource ref can be closed anyway
            logger.debug("removing resource entry: %s: %s", dead_key, dead_resources)
            await registry.remove_resource(dead_key, resource_name)

            # check if the resource is still in use in the alive keys
            if not any(elem in alive_keys for elem in other_keys):
                # remove the resource from the other keys as well
                remove_tasks = [
                    registry.remove_resource(x, resource_name) for x in other_keys
                ]
                if remove_tasks:
                    logger.debug(
                        "removing resource entry: %s: %s", other_keys, dead_resources
                    )
                    await logged_gather(*remove_tasks, reraise=False)

                logger.debug(
                    "the resources %s:%s of %s may be now safely closed",
                    resource_name,
                    resource_value,
                    dead_key,
                )
                await emit(
                    event="SIGNAL_PROJECT_CLOSE",
                    user_id=None,
                    project_uuid=resource_value,
                    app=app,
                )

                await remove_resources_if_guest_user(
                    app=app,
                    project_uuid=resource_value,
                    user_id=int(dead_key["user_id"]),
                )

    # try to remove users which were marked as GUESTS manually
    await remove_users_manually_marked_as_guests(
        app=app, alive_keys=alive_keys, dead_keys=dead_keys
    )

    # remove possible pending contianers
    await remove_orphaned_services(registry, app)


async def remove_users_manually_marked_as_guests(
    app: web.Application,
    alive_keys: List[Dict[str, str]],
    dead_keys: List[Dict[str, str]],
) -> None:
    """
    Removes all the projects associated with GUEST users in the system.
    If the user defined a TEMPLATE, this one also gets removed.
    """

    user_ids_to_ignore = set()
    for entry in chain(alive_keys, dead_keys):
        user_ids_to_ignore.add(int(entry["user_id"]))

    guest_user_ids = await get_guest_user_ids(app)
    logger.info("GUEST user id candidates to clean %s", guest_user_ids)

    for guest_user_id in guest_user_ids:
        if guest_user_id in user_ids_to_ignore:
            logger.info(
                "Ignoring user '%s' as it previously had alive or dead resource keys ",
                guest_user_id,
            )
            continue
        logger.info("Will try to remove resources for guest '%s'", guest_user_id)
        # get all projects for this user and then remove with remove_resources_if_guest_user
        user_project_uuids = await app[APP_PROJECT_DBAPI].list_all_projects_by_uuid_for_user(
            user_id=guest_user_id
        )
        logger.info(
            "Project uuids, to clean, for user '%s': '%s'",
            guest_user_id,
            user_project_uuids,
        )

        for project_uuid in user_project_uuids:
            await remove_resources_if_guest_user(
                app=app, project_uuid=project_uuid, user_id=guest_user_id,
            )


async def remove_orphaned_services(
    registry: RedisResourceRegistry, app: web.Application
) -> None:
    """Removes services which are no longer tracked in the database

    Multiple deployments can be active at the same time on the same cluster.
    This will also check the current SWARM_STACK_NAME label of the service which
    must be matching its own. The director service spawns dynamic services
    which have this new label and it also filters by this label.

    If the service is a dynamic service
    """
    logger.info("Starting orphaned services removal...")
    currently_opened_projects_node_ids = set()
    alive_keys, _ = await registry.get_all_resource_keys()
    for alive_key in alive_keys:
        resources = await registry.get_resources(alive_key)
        if "project_id" not in resources:
            continue

        project_uuid = resources["project_id"]
        node_ids = await get_workbench_node_ids_from_project_uuid(app, project_uuid)
        currently_opened_projects_node_ids.update(node_ids)

    running_interactive_services = await get_running_interactive_services(app)
    logger.info(
        "Will collect the following: %s",
        [x["service_host"] for x in running_interactive_services],
    )
    for interactive_service in running_interactive_services:
        # if not present in DB or not part of currently opened projects, can be removed
        node_id = interactive_service["service_uuid"]
        if (
            not await is_node_id_present_in_any_project_workbench(app, node_id)
            or node_id not in currently_opened_projects_node_ids
        ):
            logger.info("Will remove service %s", interactive_service["service_host"])
            try:
                await stop_service(app, node_id)
            except (ServiceNotFoundError, DirectorException) as e:
                logger.warning("Error while stopping service: %s", e)

    logger.info("Finished orphaned services removal")


async def remove_resources_if_guest_user(
    app: web.Application, project_uuid: str, user_id: int
) -> None:
    """When a guest user finishes using the platform its Posgtres
    and S3/MinIO entries need to be removed
    """
    logger.debug("Will try to remove resources for user '%s' if GUEST", user_id)
    if not await is_user_guest(app, user_id):
        logger.debug("User is not GUEST, skipping removal of its project resources")
        return

    logger.debug(
        "Removing project '%s' from the database", project_uuid,
    )

    try:
        await delete_project_from_db(app, project_uuid, user_id)
    except ProjectNotFoundError:
        logging.warning("Project '%s' not found, skipping removal", project_uuid)

    # when manually changing a user to GUEST, it might happen that it has more then one project
    try:
        await delete_user(app, user_id)
    except Exception:  # pylint: disable=broad-except
        logger.warning(
            "User '%s' still has some projects, could not be deleted", user_id
        )


async def garbage_collector_task(app: web.Application):
    keep_alive = True

    while keep_alive:
        logger.info("Starting garbage collector...")
        try:
            registry = get_registry(app)
            interval = get_garbage_collector_interval(app)
            while True:
                await collect_garbage(registry, app)
                await asyncio.sleep(interval)

        except asyncio.CancelledError:
            keep_alive = False
            logger.info("Garbage collection task was cancelled, it will not restart!")
        except Exception:  # pylint: disable=broad-except
            logger.warning(
                "There was an error during garbage collection, restarting...",
                exc_info=True,
            )
            # will wait 5 seconds before restarting to avoid restart loops
            await asyncio.sleep(5)


async def setup_garbage_collector_task(app: web.Application):
    app[APP_GARBAGE_COLLECTOR_KEY] = app.loop.create_task(garbage_collector_task(app))
    yield
    task = app[APP_GARBAGE_COLLECTOR_KEY]
    task.cancel()
    await task


def setup(app: web.Application):
    app.cleanup_ctx.append(setup_garbage_collector_task)
