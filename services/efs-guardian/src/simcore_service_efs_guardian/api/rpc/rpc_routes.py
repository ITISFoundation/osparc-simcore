from collections.abc import Awaitable, Callable

from fastapi import FastAPI


def on_app_startup(app: FastAPI) -> Callable[[], Awaitable[None]]:
    async def _start() -> None:
        assert app  # nosec

    return _start


def on_app_shutdown(app: FastAPI) -> Callable[[], Awaitable[None]]:
    async def _stop() -> None:
        assert app  # nosec

    return _stop


def setup_rpc_routes(app: FastAPI) -> None:
    app.add_event_handler("startup", on_app_startup(app))
    app.add_event_handler("shutdown", on_app_shutdown(app))
