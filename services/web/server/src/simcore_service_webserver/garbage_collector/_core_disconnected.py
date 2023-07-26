import logging

from aiohttp import web
from redis.asyncio import Redis
from servicelib.common_headers import UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE
from servicelib.utils import logged_gather

from ..projects.exceptions import ProjectLockError, ProjectNotFoundError
from ..projects.projects_api import remove_project_dynamic_services
from ..redis import get_redis_lock_manager_client
from ..resource_manager.registry import RedisResourceRegistry
from ._core_guests import remove_guest_user_with_all_its_resources
from .settings import GUEST_USER_RC_LOCK_FORMAT

_logger = logging.getLogger(__name__)


async def remove_disconnected_user_resources(
    registry: RedisResourceRegistry, app: web.Application
) -> None:
    lock_manager: Redis = get_redis_lock_manager_client(app)

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
    _logger.debug("potential dead keys: %s", dead_keys)

    # clean up all resources of expired keys
    for dead_key in dead_keys:
        # Skip locked keys for the moment
        try:
            user_id = int(dead_key["user_id"])
        except (KeyError, ValueError):  # noqa: PERF203
            continue

        if await lock_manager.lock(
            GUEST_USER_RC_LOCK_FORMAT.format(user_id=user_id)
        ).locked():
            _logger.info(
                "Skipping garbage-collecting %s since it is still locked",
                f"{user_id=}",
            )
            continue

        # (0) If key has no resources => remove from registry and continue
        dead_key_resources = await registry.get_resources(dead_key)
        if not dead_key_resources:
            await registry.remove_key(dead_key)
            continue

        # (1,2) CAREFULLY releasing every resource acquired by the expired key
        _logger.info(
            "%s expired. Checking resources to cleanup",
            f"{dead_key=}",
        )

        for resource_name, resource_value in dead_key_resources.items():
            # Releasing a resource consists of two steps
            #   - (1) release actual resource (e.g. stop service, close project, deallocate memory, etc)
            #   - (2) remove resource field entry in expired key registry after (1) is completed.

            # collects a list of keys for (2)
            keys_to_update = [
                dead_key,
            ]

            # Every resource might be SHARED with other keys.
            # In that case, the resource is released by THE LAST DYING KEY
            # (we could call this the "last-standing-man" pattern! :-) )
            #
            other_keys_with_this_resource = [
                k
                for k in await registry.find_keys((resource_name, f"{resource_value}"))
                if k != dead_key
            ]
            is_resource_still_in_use: bool = any(
                k in alive_keys for k in other_keys_with_this_resource
            )

            # FIXME: if the key is dead, shouldn't we still delete the field entry from the expired key regisitry?

            if not is_resource_still_in_use:
                # adds the remaining resource entries for (2)
                keys_to_update.extend(other_keys_with_this_resource)

                # (1) releasing acquired resources
                _logger.info(
                    "(1) Releasing resource %s:%s acquired by expired %s",
                    f"{resource_name=}",
                    f"{resource_value=}",
                    f"{dead_key!r}",
                )

                if resource_name == "project_id":
                    # inform that the project can be closed on the backend side
                    #
                    try:
                        await remove_project_dynamic_services(
                            user_id=user_id,
                            project_uuid=f"{resource_value}",
                            app=app,
                            simcore_user_agent=UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE,
                            user_name={
                                "first_name": "garbage",
                                "last_name": "collector",
                            },
                        )

                    except (ProjectNotFoundError, ProjectLockError) as err:
                        _logger.warning(
                            (
                                "Could not remove project interactive services user_id=%s "
                                "project_uuid=%s. Check the logs above for details [%s]"
                            ),
                            user_id,
                            resource_value,
                            err,
                        )

                # ONLY GUESTS: if this user was a GUEST also remove it from the database
                # with the only associated project owned
                # FIXME: if a guest can share, it will become permanent user!
                await remove_guest_user_with_all_its_resources(
                    app=app,
                    user_id=user_id,
                )

            # (2) remove resource field in collected keys since (1) is completed
            _logger.info(
                "(2) Removing field for released resource %s:%s from registry keys: %s",
                f"{resource_name=}",
                f"{resource_value=}",
                keys_to_update,
            )
            await logged_gather(
                *[
                    registry.remove_resource(key, resource_name)
                    for key in keys_to_update
                ],
                reraise=False,
            )

            # NOTE:
            #   - if releasing a resource (1) fails, annotations in registry allows GC to try in next round
            #   - if any task in (2) fails, GC will clean them up in next round as well
            #   - if all resource fields are removed from a key, next GC iteration will remove the key (see (0))
