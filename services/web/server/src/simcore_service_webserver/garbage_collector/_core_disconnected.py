import logging

from aiohttp import web
from models_library.projects import ProjectID
from pydantic import TypeAdapter
from servicelib.common_headers import UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE
from servicelib.utils import logged_gather

from ..projects import _projects_service
from ..projects.exceptions import ProjectLockError, ProjectNotFoundError
from ..redis import get_redis_lock_manager_client
from ..resource_manager.registry import (
    RedisResourceRegistry,
)
from .settings import GUEST_USER_RC_LOCK_FORMAT

_logger = logging.getLogger(__name__)


async def remove_disconnected_user_resources(
    registry: RedisResourceRegistry, app: web.Application
) -> None:
    lock_manager = get_redis_lock_manager_client(app)

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

    _, dead_user_sessions = await registry.get_all_resource_keys()
    _logger.debug("potential dead keys: %s", dead_user_sessions)

    # clean up all resources of expired keys
    for dead_session in dead_user_sessions:
        user_id = int(dead_session["user_id"])

        if await lock_manager.lock(
            GUEST_USER_RC_LOCK_FORMAT.format(user_id=user_id)
        ).locked():
            _logger.info(
                "Skipping garbage-collecting %s since it is still locked",
                f"{user_id=}",
            )
            continue

        # (0) If key has no resources => remove from registry and continue
        resources = await registry.get_resources(dead_session)
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
                    _logger.info(
                        "Closing project '%s' of user %s", resource_value, user_id
                    )
                    await _projects_service.close_project_for_user(
                        user_id,
                        TypeAdapter(ProjectID).validate_python(f"{resource_value}"),
                        dead_session["client_session_id"],
                        app,
                        simcore_user_agent=UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE,
                        wait_for_service_closed=True,
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
