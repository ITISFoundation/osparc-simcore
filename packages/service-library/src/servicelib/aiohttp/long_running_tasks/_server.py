import logging
from typing import AsyncGenerator, Callable, Optional

from aiohttp import web
from pydantic import PositiveFloat

from ...long_running_tasks._task import TasksManager
from ._constants import APP_LONG_RUNNING_TASKS_MANAGER_KEY, MINUTE
from ._error_handlers import base_long_running_error_handler
from ._routes import routes

log = logging.getLogger(__name__)


def setup(
    app: web.Application,
    *,
    router_prefix: str,
    handlers_decorator: Optional[Callable] = None,
    stale_task_check_interval_s: PositiveFloat = 1 * MINUTE,
    stale_task_detect_timeout_s: PositiveFloat = 5 * MINUTE,
) -> None:
    """
    - `router_prefix` APIs are mounted on `/...`, this
        will change them to be mounted as `{router_prefix}/...`
    - `stale_task_check_interval_s` interval at which the
        TaskManager checks for tasks which are no longer being
        actively monitored by a client
    - `stale_task_detect_timeout_s` interval after which a
        task is considered stale
    """

    async def on_startup(app: web.Application) -> AsyncGenerator[None, None]:
        # add routing paths
        for route in routes:
            app.router.add_route(
                route.method,  # type: ignore
                f"{router_prefix}{route.path}",  # type: ignore
                handlers_decorator(route.handler) if handlers_decorator else route.handler,  # type: ignore
                **route.kwargs,  # type: ignore
            )
        # app.router.add_routes(routes)

        # add components to state
        app[
            APP_LONG_RUNNING_TASKS_MANAGER_KEY
        ] = long_running_task_manager = TasksManager(
            stale_task_check_interval_s=stale_task_check_interval_s,
            stale_task_detect_timeout_s=stale_task_detect_timeout_s,
        )

        # add error handlers
        app.middlewares.append(base_long_running_error_handler)

        yield

        # cleanup
        await long_running_task_manager.close()

    app.cleanup_ctx.append(on_startup)
