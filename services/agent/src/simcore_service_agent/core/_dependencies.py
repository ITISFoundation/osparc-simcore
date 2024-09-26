""" Free functions to inject dependencies in routes handlers
"""

from typing import Annotated, cast

from fastapi import Depends, FastAPI, Request

from .settings import ApplicationSettings


def get_application(request: Request) -> FastAPI:
    return cast(FastAPI, request.app)


def get_settings(
    app: Annotated[FastAPI, Depends(get_application)]
) -> ApplicationSettings:
    assert isinstance(app.state.settings, ApplicationSettings)  # nosec
    return app.state.settings
