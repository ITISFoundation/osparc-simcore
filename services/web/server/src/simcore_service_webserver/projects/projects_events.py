import logging

from aiohttp import web
from servicelib.observer import event_registry as _event_registry
from servicelib.observer import observe
from servicelib.utils import logged_gather

from ..resource_manager.websocket_manager import PROJECT_ID_KEY, managed_resource
from .projects_api import retrieve_and_notify_project_locked_state

logger = logging.getLogger(__name__)


@observe(event="SIGNAL_USER_DISCONNECTED")
async def on_user_disconnected(
    user_id: int, client_session_id: str, app: web.Application
) -> None:
    # check if there is a project resource
    with managed_resource(user_id, client_session_id, app) as rt:
        list_projects: list[str] = await rt.find(PROJECT_ID_KEY)

    await logged_gather(
        *[
            retrieve_and_notify_project_locked_state(
                user_id, prj, app, notify_only_prj_user=True
            )
            for prj in list_projects
        ]
    )


def setup_project_events(_app: web.Application):
    # For the moment, this is only used as a placeholder to import this file
    # This way the functions above are registered as handlers of a give event
    # using the @observe decorator
    assert on_user_disconnected  # nosec
    assert on_user_disconnected in _event_registry.values()  # nosec

    logger.info("Registered events: %s", _event_registry.keys())
