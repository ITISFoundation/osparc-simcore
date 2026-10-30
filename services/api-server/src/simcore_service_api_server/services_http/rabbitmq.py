from collections.abc import AsyncIterator
from contextlib import AsyncExitStack

from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager, State
from servicelib.fastapi.rabbitmq_lifespan import (
    configure_rabbitmq_client as _configure_rabbitmq_client,
)
from servicelib.fastapi.rabbitmq_lifespan import (
    configure_rabbitmq_rpc_client as _configure_rabbitmq_rpc_client,
)
from settings_library.rabbit import RabbitSettings

from ..api.dependencies.rabbitmq import get_rabbitmq_rpc_client
from ..core.health_checker import ApiServerHealthChecker
from ..services_http.log_streaming import LogDistributor
from ..services_rpc import resource_usage_tracker, wb_api_server


def configure_rabbitmq(
    app_lifespan: LifespanManager[FastAPI],
    *,
    settings: RabbitSettings | None,
) -> None:
    _configure_rabbitmq_client(
        app_lifespan,
        settings=settings,
        client_name="api_server",
        wait_for_connectivity=True,
    )
    _configure_rabbitmq_rpc_client(
        app_lifespan,
        settings=settings,
        client_name="api_server_rpc_client",
        wait_for_connectivity=False,
    )
    if settings is None:
        return

    async def _rabbitmq_lifespan(app: FastAPI) -> AsyncIterator[State]:
        app.state.health_checker = None
        app.state.log_distributor = None
        async with AsyncExitStack() as exit_stack:
            app.state.log_distributor = LogDistributor(app.state.rabbitmq_client)
            await app.state.log_distributor.setup()
            exit_stack.push_async_callback(app.state.log_distributor.teardown)

            app.state.health_checker = ApiServerHealthChecker(
                log_distributor=app.state.log_distributor,
                rabbit_client=app.state.rabbitmq_client,
                rabbitmq_rpc_client=app.state.rabbitmq_rpc_client,
                timeout_seconds=app.state.settings.API_SERVER_HEALTH_CHECK_TASK_TIMEOUT_SECONDS,
                allowed_health_check_failures=app.state.settings.API_SERVER_ALLOWED_HEALTH_CHECK_FAILURES,
            )
            exit_stack.push_async_callback(app.state.health_checker.teardown)
            await app.state.health_checker.setup(app.state.settings.API_SERVER_HEALTH_CHECK_TASK_PERIOD_SECONDS)

            # setup rpc clients
            resource_usage_tracker.setup(app, get_rabbitmq_rpc_client(app))
            wb_api_server.setup(app, get_rabbitmq_rpc_client(app))

            yield {}

    app_lifespan.add(_rabbitmq_lifespan)
