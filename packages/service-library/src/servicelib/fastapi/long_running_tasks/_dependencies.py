from fastapi import Request

from ._manager import FastAPILongRunningManager


def get_long_running_manager(request: Request) -> FastAPILongRunningManager:
    assert isinstance(
        request.app.state.long_running_manager, FastAPILongRunningManager
    )  # nosec
    return request.app.state.long_running_manager
