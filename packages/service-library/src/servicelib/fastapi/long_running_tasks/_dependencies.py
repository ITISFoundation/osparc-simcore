from fastapi import FastAPI, Request

from ._manager import FastAPILongRunningManager


def get_long_running_manager(request: Request) -> FastAPILongRunningManager:
    return get_long_running_manager_from_app(request.app)


def get_long_running_manager_from_app(app: FastAPI) -> FastAPILongRunningManager:
    assert isinstance(
        app.state.long_running_manager, FastAPILongRunningManager
    )  # nosec
    return app.state.long_running_manager
