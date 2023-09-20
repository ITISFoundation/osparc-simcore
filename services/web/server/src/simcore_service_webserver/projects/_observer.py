""" Handlers to events registered in servicelib.observer.event_registry

"""

import logging

from aiohttp import web
from models_library.products import ProductName
from models_library.projects import ProjectID
from servicelib.aiohttp.observer import (
    registed_observers_report,
    register_observer,
    setup_observer_registry,
)
from servicelib.utils import logged_gather

from ..notifications import project_logs
from ..resource_manager.user_sessions import PROJECT_ID_KEY, managed_resource
from .projects_api import retrieve_and_notify_project_locked_state

_logger = logging.getLogger(__name__)


async def _on_user_disconnected(
    user_id: int,
    client_session_id: str,
    app: web.Application,
    product_name: ProductName,  # pylint: disable=unused-argument
) -> None:
    # check if there is a project resource
    with managed_resource(user_id, client_session_id, app) as user_session:
        projects: list[str] = await user_session.find(PROJECT_ID_KEY)

    assert len(projects) <= 1, "At the moment, at most one project per session"  # nosec

    await logged_gather(
        *[project_logs.unsubscribe(app, ProjectID(prj)) for prj in projects]
    )

    await logged_gather(
        *[
            retrieve_and_notify_project_locked_state(
                user_id, prj, app, notify_only_prj_user=True
            )
            for prj in projects
        ]
    )


def setup_project_observer_events(app: web.Application) -> None:
    setup_observer_registry(app)

    register_observer(app, _on_user_disconnected, event="SIGNAL_USER_DISCONNECTED")

    _logger.info(
        "App registered events (at this point):\n%s", registed_observers_report(app)
    )
