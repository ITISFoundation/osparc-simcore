import logging

from aiohttp import web
from redis.asyncio import Redis
from servicelib.common_headers import UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE
from servicelib.utils import logged_gather

from ..projects.exceptions import ProjectLockError, ProjectNotFoundError
from ..projects.projects_api import remove_project_dynamic_services
from ..redis import get_redis_lock_manager_client
from ..resource_manager.registry import (
    RedisResourceRegistry,
    ResourcesDict,
    UserSessionDict,
)
from ._core_guests import remove_guest_user_with_all_its_resources
from .settings import GUEST_USER_RC_LOCK_FORMAT

_logger = logging.getLogger(__name__)


async def remove_disconnected_user_resources(
    registry: RedisResourceRegistry, app: web.Application
) -> None:
    lock_manager: Redis = get_redis_lock_manager_client(app)

    #
    # In redis jargon, every entry is denoted as "key"
    # - A key can contain one or more fields: name-value pairs
    # - A key can have a limited livespan by setting the Time-to-live (TTL) which
    #       is automatically decreasing
    # - Every user can open multiple sessions (e.g. in different tabs and/or browser) and
    #   each session is hierarchically represented in the redis registry with two keys:
    #     - "alive" is a string that keeps a TLL of the user session
    #     - "resources" is a hash toto keep project and websocket ids
    #

    all_session_alive, all_sessions_dead = await registry.get_all_resource_keys()
    _logger.debug("potential dead keys: %s", all_sessions_dead)

    # clean up all resources of expired keys
    for dead_session in all_sessions_dead:

        try:
            user_id = int(dead_session["user_id"])
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
        resources: ResourcesDict = await registry.get_resources(dead_session)
        if not resources:
            await registry.remove_key(dead_session)
            continue

        # (1,2) CAREFULLY releasing every resource acquired by the expired key
        _logger.info(
            "%s expired. Checking resources to cleanup",
            f"{dead_session=}",
        )

        for resource_name, resource_value in resources.items():
            # Releasing a resource consists of two steps
            #   - (1) release actual resource (e.g. stop service, close project, deallocate memory, etc)
            #   - (2) remove resource field entry in expired key registry after (1) is completed.

            # collects a list of keys for (2)
            keys_to_update = [
                dead_session,
            ]

            # Every resource might be SHARED with other keys.
            # In that case, the resource is released by THE LAST DYING KEY
            # (we could call this the "last-standing-man" pattern! :-) )
            #
            other_sessions_with_this_resource: list[UserSessionDict] = [
                k
                for k in await registry.find_keys((resource_name, f"{resource_value}"))
                if k != dead_session
            ]
            is_resource_still_in_use: bool = any(
                k in all_session_alive for k in other_sessions_with_this_resource
            )

            if not is_resource_still_in_use:
                # adds the remaining resource entries for (2)
                keys_to_update.extend(other_sessions_with_this_resource)

                # (1) releasing acquired resources
                _logger.info(
                    "(1) Releasing resource %s:%s acquired by expired %s",
                    f"{resource_name=}",
                    f"{resource_value=}",
                    f"{dead_session!r}",
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
            #   - if releasing a resource (1) fails, the resource is not removed from the registry and it allows GC to try in next round
            #   - if any task in (2) fails, GC will clean them up in next round as well
            #   - if all resource fields are removed from a key, next GC iteration will remove the key (see (0))
