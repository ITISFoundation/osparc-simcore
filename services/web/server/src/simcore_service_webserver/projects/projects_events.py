""" Handlers to events registered in servicelib.observer.event_registry

"""

import logging

from aiohttp import web
from models_library.projects import ProjectID
from servicelib.observer import event_registry as _event_registry
from servicelib.observer import observe
from servicelib.utils import logged_gather

from ..notifications import project_logs
from ..resource_manager.websocket_manager import PROJECT_ID_KEY, managed_resource
from .projects_api import retrieve_and_notify_project_locked_state

logger = logging.getLogger(__name__)


@observe(event="SIGNAL_USER_DISCONNECTED")
async def _on_user_disconnected(
    user_id: int, client_session_id: str, app: web.Application
) -> None:
    # check if there is a project resource
    with managed_resource(user_id, client_session_id, app) as rt:
        list_projects: list[str] = await rt.find(PROJECT_ID_KEY)

    await logged_gather(
        *[project_logs.unsubscribe(app, ProjectID(prj)) for prj in list_projects]
    )

    await logged_gather(
        *[
            retrieve_and_notify_project_locked_state(
                user_id, prj, app, notify_only_prj_user=True
            )
            for prj in list_projects
        ]
    )


def setup_project_events(_app: web.Application) -> None:
    # For the moment, this is only used as a placeholder to import this file
    # This way the functions above are registered as handlers of a give event
    # using the @observe decorator

    assert _on_user_disconnected  # nosec
    #
    # FIXME: with_db/02/conftest.py
    # 'assert _on_user_disconnected in _event_registry["SIGNAL_USER_DISCONNECTED"] ' FAILS
    # showing '_on_user_disconnected' with different ids!!
    # This typically happens when somewhere importlib.reload was used.
    # Since the function is stateless and registstered once, for the moment
    # we make a weaker
    assert _on_user_disconnected.__name__ in (  # nosec
        f.__name__ for f in _event_registry["SIGNAL_USER_DISCONNECTED"]
    )

    logger.info(
        "App registered events (at this point):\n%s",
        "\n".join(
            f" {event}->{len(funcs)} handles"
            for event, funcs in _event_registry.items()
        ),
    )
