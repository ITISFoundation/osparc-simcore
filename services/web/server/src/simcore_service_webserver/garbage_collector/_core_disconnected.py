import logging

from aiohttp import web
from models_library.projects import ProjectID
from pydantic import TypeAdapter
from servicelib.common_headers import UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE
from servicelib.logging_utils import log_catch, log_context

from ..projects import _projects_service
from ..resource_manager.registry import (
    RedisResourceRegistry,
)

_logger = logging.getLogger(__name__)


async def remove_disconnected_user_resources(
    registry: RedisResourceRegistry, app: web.Application
) -> None:
    # NOTE:
    # Each user session is represented in the redis registry with two keys:
    # - "alive" is a string that keeps a TTL of the user session
    # - "resources" is a redis hash to keep project and websocket ids attached to the user session
    # when the alive key expires, it means the user session is disconnected
    # and the resources attached to that user session shall be closed and removed
    #

    _, dead_user_sessions = await registry.get_all_resource_keys()
    _logger.debug("potential dead keys: %s", dead_user_sessions)

    # clean up all resources of expired keys
    for dead_session in dead_user_sessions:
        user_id = dead_session.user_id

        # (0) If key has no resources => remove from registry and continue
        resources = await registry.get_resources(dead_session)
        if not resources:
            await registry.remove_key(dead_session)
            continue

        for resource_name, resource_value in resources.items():
            # (1) releasing acquired resources (currently only projects),
            # that means closing project for the disconnected user
            _logger.info(
                "(1) Releasing resource %s:%s acquired by expired %s",
                f"{resource_name=}",
                f"{resource_value=}",
                f"{dead_session!r}",
            )

            if resource_name == "project_id":
                # inform that the project can be closed on the backend side
                #
                project_id = TypeAdapter(ProjectID).validate_python(resource_value)
                with (
                    log_catch(_logger, reraise=False),
                    log_context(
                        _logger,
                        logging.INFO,
                        f"Closing project {project_id} for user {user_id=}",
                    ),
                ):
                    await _projects_service.close_project_for_user(
                        user_id=user_id,
                        project_uuid=project_id,
                        client_session_id=dead_session.client_session_id,
                        app=app,
                        simcore_user_agent=UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE,
                        wait_for_service_closed=True,
                    )
