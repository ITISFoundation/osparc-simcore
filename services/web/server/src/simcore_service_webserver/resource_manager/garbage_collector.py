import asyncio
import logging
from contextlib import suppress
from itertools import chain
from typing import Dict, List, Tuple

from aiohttp import web
from aiopg.sa.result import RowProxy
from aioredlock import Aioredlock

from servicelib.observer import emit
from servicelib.utils import logged_gather
from simcore_service_webserver import users_exceptions
from simcore_service_webserver.db_models import GroupType
from simcore_service_webserver.director.director_api import (
    get_running_interactive_services,
    stop_service,
)
from simcore_service_webserver.director.director_exceptions import (
    DirectorException,
    ServiceNotFoundError,
)
from simcore_service_webserver.groups_api import get_group_from_gid
from simcore_service_webserver.projects.projects_api import (
    delete_project_from_db,
    get_project_for_user,
    get_workbench_node_ids_from_project_uuid,
    is_node_id_present_in_any_project_workbench,
)
from simcore_service_webserver.projects.projects_db import (
    APP_PROJECT_DBAPI,
    ProjectAccessRights,
)
from simcore_service_webserver.projects.projects_exceptions import ProjectNotFoundError
from simcore_service_webserver.users_api import (
    delete_user,
    get_guest_user_ids_and_names,
    get_user,
    get_user_id_from_gid,
    is_user_guest,
)
from simcore_service_webserver.users_to_groups_api import get_users_for_gid

from .config import (
    APP_CLIENT_REDIS_LOCK_KEY,
    APP_GARBAGE_COLLECTOR_KEY,
    GUEST_USER_RC_LOCK_FORMAT,
    get_garbage_collector_interval,
)
from .registry import RedisResourceRegistry, get_registry

logger = logging.getLogger(__name__)


async def setup_garbage_collector_task(app: web.Application):
    loop = asyncio.get_event_loop()
    app[APP_GARBAGE_COLLECTOR_KEY] = loop.create_task(garbage_collector_task(app))
    yield
    task = app[APP_GARBAGE_COLLECTOR_KEY]
    task.cancel()
    await task


def setup_garbage_collector(app: web.Application):
    app.cleanup_ctx.append(setup_garbage_collector_task)


async def garbage_collector_task(app: web.Application):
    keep_alive = True

    while keep_alive:
        logger.info("Starting garbage collector...")
        try:
            interval = get_garbage_collector_interval(app)
            while True:
                await collect_garbage(app)
                await asyncio.sleep(interval)

        except asyncio.CancelledError:
            keep_alive = False
            logger.info("Garbage collection task was cancelled, it will not restart!")

        except Exception:  # pylint: disable=broad-except
            logger.warning(
                "There was an error during garbage collection, restarting...",
                exc_info=True,
            )
            # will wait 5 seconds to recover before restarting to avoid restart loops
            # - it might be that db/redis is down, etc
            #
            await asyncio.sleep(5)


async def collect_garbage(app: web.Application):
    """
    Garbage collection has the task of removing trash (i.e. unused resources) from the system. The trash
    can be divided in:

    - Websockets & Redis (used to keep track of current active connections)
    - GUEST users (used for temporary access to the system which are created on the fly)
    - Deletion of users. If a user needs to be deleted it can be set as GUEST in the database

    The resources are Redis entries where all information regarding all the
    websocket identifiers for all opened tabs accross all browser for each user
    are stored.

    The alive/dead keys are normal Redis keys. To each key an ALIVE key is associated,
    which has an assigned TTL (Time To Live). The browser will call the `client_heartbeat` websocket
    endpoint to refresh the TTL, thus declaring that the user (websocket connection) is
    still active. The `resource_deletion_timeout_seconds` is the TTL of the key.

    The field `garbage_collection_interval_seconds` defines the interval at which this
    function will be called.
    """
    logger.info("Collecting garbage...")

    registry: RedisResourceRegistry = get_registry(app)

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

    # Temporary disabling GC to until the dynamic service
    # safe function is invoked by the GC. This will avoid
    # data loss for current users.
    await remove_orphaned_services(registry, app)


async def remove_disconnected_user_resources(
    registry: RedisResourceRegistry, app: web.Application
) -> None:
    lock_manager: Aioredlock = app[APP_CLIENT_REDIS_LOCK_KEY]

    #
    # In redis jargon, every entry is denoted as "key"
    #   - A key can contain one or more fields: name-value pairs
    #   - A key can have a limited livespan by setting the Time-to-live (TTL) which
    #       is automatically decreasing
    #
    # - Every user can open multiple sessions (e.g. in different tabs and/or browser) and
    #   each session is hierarchically represented in the redis registry with two keys:
    #     - "alive" that keeps a TLL
    #     - "resources" to keep a list of resources
    # - A resource is defined as something that can be acquire/released and in some times
    #   also shared. For instance, websocket_id, project_id are resource ids. The first is established
    #   between the web-client and the backend.
    #
    # - If all sessions of a GUEST user close (i.e. "alive" key expires)
    #
    #

    # alive_keys = currently "active" users
    # dead_keys = users considered as "inactive" (i.e. resource has expired since TLL reached 0!)
    # these keys hold references to more than one websocket connection ids
    # the websocket ids are referred to as resources (but NOT the only resource)

    alive_keys, dead_keys = await registry.get_all_resource_keys()
    logger.debug("potential dead keys: %s", dead_keys)

    # clean up all resources of expired keys
    for dead_key in dead_keys:

        # Skip locked keys for the moment
        user_id = int(dead_key["user_id"])
        if await lock_manager.is_locked(
            GUEST_USER_RC_LOCK_FORMAT.format(user_id=user_id)
        ):
            logger.debug(
                "Skipping garbage-collecting user '%d' since it is still locked",
                user_id,
            )
            continue

        # (0) If key has no resources => remove from registry and continue
        dead_key_resources = await registry.get_resources(dead_key)
        if not dead_key_resources:
            await registry.remove_key(dead_key)
            continue

        # (1,2) CAREFULLY releasing every resource acquired by the expired key
        logger.debug(
            "Key '%s' expired. Cleaning the following resources: '%s'",
            dead_key,
            dead_key_resources,
        )

        for resource_name, resource_value in dead_key_resources.items():

            # Releasing a resource consists of two steps
            #   - (1) release actual resource (e.g. stop service, close project, deallocate memory, etc)
            #   - (2) remove resource field entry in expired key registry after (1) is completed.

            # collects a list of keys for (2)
            keys_to_update = [
                dead_key,
            ]

            # Every resource might be shared with other keys.
            # In that case, the resource is released by THE LAST DYING KEY
            # (we could call this the "last-standing-man" pattern! :-) )
            #
            other_keys_with_this_resource = [
                k
                for k in await registry.find_keys((resource_name, resource_value))
                if k != dead_key
            ]
            is_resource_still_in_use: bool = any(
                k in alive_keys for k in other_keys_with_this_resource
            )

            if not is_resource_still_in_use:

                # adds the remaining resource entries for (2)
                keys_to_update.extend(other_keys_with_this_resource)

                # (1) releasing acquired resources
                logger.info(
                    "(1) Releasing resource %s:%s acquired by expired key %s",
                    resource_name,
                    resource_value,
                    dead_key,
                )

                if resource_name == "project_id":
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
                    app=app,
                    user_id=int(dead_key["user_id"]),
                )

            # (2) remove resource field in collected keys since (1) is completed
            logger.info(
                "(2) Removing resource %s field entry from registry keys: %s",
                resource_name,
                keys_to_update,
            )
            with suppress(asyncio.CancelledError):
                on_released_tasks = [
                    registry.remove_resource(key, resource_name)
                    for key in keys_to_update
                ]
                await logged_gather(*on_released_tasks, reraise=False)

            # NOTE:
            #   - if releasing a resource (1) fails, annotations in registry allows GC to try in next round
            #   - if any task in (2) fails, GC will clean them up in next round as well
            #   - if all resource fields are removed from a key, next GC iteration will remove the key (see (0))


async def remove_users_manually_marked_as_guests(
    registry: RedisResourceRegistry, app: web.Application
) -> None:
    """
    Removes all the projects associated with GUEST users in the system.
    If the user defined a TEMPLATE, this one also gets removed.
    """
    lock_manager: Aioredlock = app[APP_CLIENT_REDIS_LOCK_KEY]

    # collects all users with registed sessions
    alive_keys, dead_keys = await registry.get_all_resource_keys()

    user_ids_to_ignore = set()
    for entry in chain(alive_keys, dead_keys):
        user_ids_to_ignore.add(int(entry["user_id"]))

    # Prevent creating this list if a guest user
    guest_users: List[Tuple[int, str]] = await get_guest_user_ids_and_names(app)
    logger.info("GUEST user candidates to clean %s", guest_users)

    for guest_user_id, guest_user_name in guest_users:
        if guest_user_id in user_ids_to_ignore:
            logger.info(
                "Ignoring user '%s' as it previously had alive or dead resource keys ",
                guest_user_id,
            )
            continue

        lock_during_construction: bool = await lock_manager.is_locked(
            GUEST_USER_RC_LOCK_FORMAT.format(user_id=guest_user_name)
        )

        lock_during_initialization: bool = await lock_manager.is_locked(
            GUEST_USER_RC_LOCK_FORMAT.format(user_id=guest_user_id)
        )

        if lock_during_construction or lock_during_initialization:
            logger.debug(
                "Skipping garbage-collecting user '%s','%s' since it is still locked",
                guest_user_id,
                guest_user_name,
            )
            continue

        await remove_guest_user_with_all_its_resources(
            app=app,
            user_id=guest_user_id,
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


async def remove_guest_user_with_all_its_resources(
    app: web.Application, user_id: int
) -> None:
    """Removes a GUEST user with all its associated projects and S3/MinIO files"""
    logger.debug("Will try to remove resources for user '%s' if GUEST", user_id)
    if not await is_user_guest(app, user_id):
        logger.debug("User is not GUEST, skipping cleanup")
        return

    try:
        await remove_all_projects_for_user(app=app, user_id=user_id)
        await remove_user(app=app, user_id=user_id)
    except Exception as e:  # pylint: disable=broad-except
        logger.warning("%s", e)
        logger.warning(
            "Could not remove GUEST with id=%s. Check the logs above for details",
            user_id,
        )


async def remove_all_projects_for_user(app: web.Application, user_id: int) -> None:
    """
    Goes through all the projects and will try to remove them but first it will check if
    the project is shared with others.
    Based on the given access rights it will deltermine the action to take:
    - if other users have read access & execute access it will get deleted
    - if other users have write access the project's owner will be changed to a new owner:
        - if the project is directly shared with a one or more users, one of these
            will be picked as the new owner
        - if the project is not shared with any user but with groups of users, one
            of the users inside the group (which currently exists) will be picked as
            the new owner
    """
    # recover user's primary_gid
    try:
        project_owner: Dict = await get_user(app=app, user_id=user_id)
    except users_exceptions.UserNotFoundError:
        logger.warning(
            "Could not recover user data for user '%s', stopping removal of projects!",
            user_id,
        )
        return
    user_primary_gid: str = str(project_owner["primary_gid"])

    # fetch all projects for the user
    user_project_uuids = await app[
        APP_PROJECT_DBAPI
    ].list_all_projects_by_uuid_for_user(user_id=user_id)
    logger.info(
        "Project uuids, to clean, for user '%s': '%s'",
        user_id,
        user_project_uuids,
    )

    for project_uuid in user_project_uuids:
        logger.debug(
            "Removing or transfering project '%s'",
            project_uuid,
        )
        try:
            project: Dict = await get_project_for_user(
                app=app,
                project_uuid=project_uuid,
                user_id=user_id,
                include_templates=True,
            )
        except web.HTTPNotFound:
            logger.warning(
                "Could not recover project data for project_uuid '%s', skipping...",
                project_uuid,
            )
            continue

        new_project_owner_gid = await get_new_project_owner_gid(
            app=app,
            project_uuid=project_uuid,
            user_id=user_id,
            user_primary_gid=user_primary_gid,
            project=project,
        )

        if new_project_owner_gid is None:
            # when no new owner is found just remove the project
            logger.info(
                "The project can be removed as is not shared with write access with other users"
            )
            try:
                await delete_project_from_db(app, project_uuid, user_id)
            except ProjectNotFoundError:
                logging.warning(
                    "Project '%s' not found, skipping removal", project_uuid
                )
            continue

        # Try to change the project owner and remove access rights from the current owner
        await replace_current_owner(
            app=app,
            project_uuid=project_uuid,
            user_primary_gid=user_primary_gid,
            new_project_owner_gid=new_project_owner_gid,
            project=project,
        )


async def get_new_project_owner_gid(
    app: web.Application,
    project_uuid: str,
    user_id: int,
    user_primary_gid: int,
    project: RowProxy,
) -> str:
    """Goes through the access rights and tries to find a new suitable owner.
    The first viable user is selected as a new owner.
    In order to become a new owner the user must have write access right.
    """

    access_rights = project["accessRights"]
    other_users_access_rights = set(access_rights.keys()) - {user_primary_gid}
    logger.debug(
        "Processing other user and groups access rights '%s'",
        other_users_access_rights,
    )

    # Selecting a new project owner
    # divide permissions between types of groups
    standard_groups = {}  # groups of users, multiple users can be part of this
    primary_groups = {}  # each individual user has a unique primary group
    for other_gid in other_users_access_rights:
        group = await get_group_from_gid(app=app, gid=int(other_gid))
        # only process for users and groups with write access right
        if group is None:
            continue
        if access_rights[other_gid]["write"] is not True:
            continue

        if group.type == GroupType.STANDARD:
            standard_groups[other_gid] = access_rights[other_gid]
        elif group.type == GroupType.PRIMARY:
            primary_groups[other_gid] = access_rights[other_gid]

    logger.debug(
        "Possible new owner groups: standard='%s', primary='%s'",
        standard_groups,
        primary_groups,
    )

    new_project_owner_gid = None
    # the primary group contains the users which which the project was directly shared
    if len(primary_groups) > 0:
        # fetch directly from the direct users with which the project is shared with
        new_project_owner_gid = list(primary_groups.keys())[0]
    # fallback to the groups search if the user does not exist
    if len(standard_groups) > 0 and new_project_owner_gid is None:
        new_project_owner_gid = await fetch_new_project_owner_from_groups(
            app=app,
            standard_groups=standard_groups,
            user_id=user_id,
        )

    logger.info(
        "Will move project '%s' to user with gid '%s', if user exists",
        project_uuid,
        new_project_owner_gid,
    )

    return new_project_owner_gid


async def fetch_new_project_owner_from_groups(
    app: web.Application, standard_groups: Dict, user_id: int
) -> int:
    """Iterate over all the users in a group and if the users exists in the db
    return its gid"""

    # fetch all users in the group and then get their gid to put in here
    # go through user_to_groups table and fetch all uid for matching gid
    for group_gid in standard_groups.keys():
        # remove the current owner from the bunch
        target_group_users = await get_users_for_gid(app=app, gid=group_gid) - {user_id}
        logger.error("Found group users '%s'", target_group_users)

        for possible_user_id in target_group_users:
            # check if the possible_user is still present in the db
            try:
                possible_user = await get_user(app=app, user_id=possible_user_id)
                return possible_user["primary_gid"]
            except users_exceptions.UserNotFoundError:
                logger.warning(
                    "Could not find new owner '%s' will try a new one",
                    possible_user_id,
                )
        return None


async def replace_current_owner(
    app: web.Application,
    project_uuid: str,
    user_primary_gid: int,
    new_project_owner_gid: str,
    project: RowProxy,
) -> None:
    try:
        new_project_owner_id = await get_user_id_from_gid(
            app=app, primary_gid=int(new_project_owner_gid)
        )
    except Exception:  # pylint: disable=broad-except
        logger.exception(
            "Could not recover new user id from gid %s", new_project_owner_gid
        )
        return
    # the result might me none
    if new_project_owner_id is None:
        logger.warning(
            "Could not recover a new user id from gid %s", new_project_owner_gid
        )
        return

    # unseting the project owner and saving the project back
    project["prj_owner"] = int(new_project_owner_id)
    # removing access rights entry
    del project["accessRights"][str(user_primary_gid)]
    project["accessRights"][
        str(new_project_owner_gid)
    ] = ProjectAccessRights.OWNER.value
    logger.error("Syncing back project %s", project)
    # syncing back project data
    try:
        await app[APP_PROJECT_DBAPI].update_project_without_enforcing_checks(
            project_data=project,
            project_uuid=project_uuid,
        )
    except Exception:  # pylint: disable=broad-except
        logger.exception(
            "Could not remove old owner and replaced it with user %s",
            new_project_owner_id,
        )


async def remove_user(app: web.Application, user_id: int) -> None:
    """Tries to remove a user, if the users still exists a warning message will be displayed"""
    try:
        await delete_user(app, user_id)
    except Exception:  # pylint: disable=broad-except
        logger.warning(
            "User '%s' still has some projects, could not be deleted", user_id
        )
