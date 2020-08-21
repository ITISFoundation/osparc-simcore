import asyncio
import logging
from itertools import chain

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


def setup(app: web.Application):
    app.cleanup_ctx.append(setup_garbage_collector_task)


async def setup_garbage_collector_task(app: web.Application):
    app[APP_GARBAGE_COLLECTOR_KEY] = app.loop.create_task(garbage_collector_task(app))
    yield
    task = app[APP_GARBAGE_COLLECTOR_KEY]
    task.cancel()
    await task


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


async def collect_garbage(registry: RedisResourceRegistry, app: web.Application):
    """
    Garbage collection has the task of removing trash from the system. The trash 
    can be divided in:
    
    - Websockets & Redis (used to keep track of current active connections)
    - GUEST users (used for temporary access to the system which are created on the fly)
    - deletion of users. If a user needs to be deleted it is manually marked as GUEST 
        in the database

    The resources are Redis entries where all information regarding all the
    websocket identifiers for all opened tabs accross all broser for each user
    are stored.

    The alive/dead keys are normal Redis keys. To each key and ALIVE key is associated,
    which has an assigned TTL. The browser will call the `client_heartbeat` websocket
    endpoint to refresh the TTL, thus declaring that the user (websocket connection) is
    still active. The `resource_deletion_timeout_seconds` is theTTL of the key.

    The field `garbage_collection_interval_seconds` defines the interval at which this 
    function will be called.
    """
    logger.info("collecting garbage...")

    # Removes disconnected user resources
    # Triggers signal to close possible pending opened projects
    # Removes disconnected GUEST users after they finished their sessions
    await remove_disconnected_user_resources(registry, app)

    # Users manually marked for removal:
    # if a user was manually marked as GUEST it needs to be
    # removed together with all the associated projects
    await remove_users_manually_marked_as_guests(registry, app)

    # For various reasons, some services remain pending after
    # the projects are closed or the user was disconencted.
    # This will close and remove all these services from
    # the cluster, thus freeing important resources.
    await remove_orphaned_services(registry, app)


async def remove_disconnected_user_resources(
    registry: RedisResourceRegistry, app: web.Application
) -> None:
    # alive_keys = currently "active" users
    # dead_keys = users considered as "inactive"
    # these keys hold references to more then one websocket connection ids
    # the websocket ids are referred to as resources
    alive_keys, dead_keys = await registry.get_all_resource_keys()
    logger.debug("potential dead keys: %s", dead_keys)

    # clean up all the the websocket ids for the disconnected user
    for dead_key in dead_keys:
        dead_key_resources = await registry.get_resources(dead_key)
        if not dead_key_resources:
            # no websocket associated with this user, just removing key
            await registry.remove_key(dead_key)
            continue

        logger.debug("Dead key '%s' resources: '%s'", dead_key, dead_key_resources)

        # removing all websocket references for the disconnected user
        for resource_name, resource_value in dead_key_resources.items():
            # list of other websocket references to be removed
            other_keys = [
                x
                for x in await registry.find_keys((resource_name, resource_value))
                if x != dead_key
            ]

            # it is safe to remove the current websocket entry for this user
            logger.debug("removing resource '%s' for '%s' key", resource_name, dead_key)
            await registry.remove_resource(dead_key, resource_name)

            # check if the resource is still in use in the alive keys
            if not any(elem in alive_keys for elem in other_keys):
                # remove the remaining websocket entries
                remove_tasks = [
                    registry.remove_resource(x, resource_name) for x in other_keys
                ]
                if remove_tasks:
                    logger.debug(
                        "removing resource entry: %s: %s",
                        other_keys,
                        dead_key_resources,
                    )
                    await logged_gather(*remove_tasks, reraise=False)

                logger.debug(
                    "the resources %s:%s of %s may be now safely closed",
                    resource_name,
                    resource_value,
                    dead_key,
                )
                # inform that the project can be closed on the backend side
                await emit(
                    event="SIGNAL_PROJECT_CLOSE",
                    user_id=None,
                    project_uuid=resource_value,
                    app=app,
                )

                # if this user was a GUEST also remove it from the database
                # with the only associated project owned
                await remove_guest_user_with_all_its_resources(
                    app=app, user_id=int(dead_key["user_id"]),
                )


async def remove_users_manually_marked_as_guests(
    registry: RedisResourceRegistry, app: web.Application
) -> None:
    """
    Removes all the projects associated with GUEST users in the system.
    If the user defined a TEMPLATE, this one also gets removed.
    """
    alive_keys, dead_keys = await registry.get_all_resource_keys()

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

        await remove_guest_user_with_all_its_resources(
            app=app, user_id=guest_user_id,
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


async def remove_all_projects_for_user(app: web.Application, user_id: int) -> None:
    """
    Goes through all the projects and will try to remove them but first it will check if
    the project is shared with others. 
    Based on the given access rights it will deltermine the action to take:
    - if other users have read access & execute access it will get deleted
    - if other users have write access the project's owner will be unset, 
        resulting in the project still being available to others
    """

    # TODO: apply access rights enforcement and checks
    # NEED TO REMOVE ALL THESE FOR THE USER

    # get all projects for this user and then remove with remove_guest_user_with_all_its_resources
    user_project_uuids = await app[
        APP_PROJECT_DBAPI
    ].list_all_projects_by_uuid_for_user(user_id=user_id)
    logger.info(
        "Project uuids, to clean, for user '%s': '%s'", user_id, user_project_uuids,
    )

    for project_uuid in user_project_uuids:
        try:
            logger.debug(
                "Removing project '%s' from the database", project_uuid,
            )
            # TODO: ENFORCE THE CHECKS HERE
            # - fetch the project and its access rithgt
            await delete_project_from_db(app, project_uuid, user_id)
        except ProjectNotFoundError:
            logging.warning("Project '%s' not found, skipping removal", project_uuid)


async def remove_user(app: web.Application, user_id: int) -> None:
    """Tries to remove a user, if the users still exists a warning message will be displayed"""
    try:
        await delete_user(app, user_id)
    except Exception:  # pylint: disable=broad-except
        logger.warning(
            "User '%s' still has some projects, could not be deleted", user_id
        )


async def remove_guest_user_with_all_its_resources(
    app: web.Application, user_id: int
) -> None:
    """Removes a GUUEST user with all its associated projects and S3/MinIO files"""
    logger.debug("Will try to remove resources for user '%s' if GUEST", user_id)
    if not await is_user_guest(app, user_id):
        logger.debug("User is not GUEST, skipping cleanup")
        return

    await remove_all_projects_for_user(app=app, user_id=user_id)
    await remove_user(app=app, user_id=user_id)


# TODO: tests for garbage collector
# - a User with more then 2 projects
# - a user without projects
# - a user with just 1 project
#
#  The user can be:
# - connected via browser (websocket connection is up)
# - disconnected (no websocket connection)

# When DELETING the project check:
# - if the project has multiple owners (it is shared with more then 1 person looking at the access rights),
#   set the user to NULL, if it is just a VIEWER user, then we do not care and remove it
# - if the project is not shared (only user primary_gid in access rights) remove it
