from fastapi import Depends, FastAPI
from fastapi.requests import Request

from ...core.settings import AppSettings, DirectorSettings
from ...services.director import AuthSession

UNAVAILBLE_MSG = "backend service is disabled or unreachable"


def _get_app(request: Request) -> FastAPI:
    return request.app


def _get_settings(request: Request) -> DirectorSettings:
    app_settings: AppSettings = request.app.state.settings
    return app_settings.director


def get_director_session(app: FastAPI = Depends(_get_app),) -> AuthSession:
    """
        Lifetime of AuthSession wrapper is one request because it needs different session cookies
        Lifetime of embedded client is attached to the app lifetime
    """
    import pdb

    pdb.set_trace()
    return AuthSession.create(app)
