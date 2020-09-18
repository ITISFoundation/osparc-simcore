from fastapi import Depends, FastAPI
from fastapi.requests import Request

from ...core.settings import AppSettings, DirectorSettings
from ...services.director import DirectorApi


def _get_app(request: Request) -> FastAPI:
    return request.app


def _get_settings(request: Request) -> DirectorSettings:
    app_settings: AppSettings = request.app.state.settings
    return app_settings.director


def get_director_api(
    app: FastAPI = Depends(_get_app),
) -> DirectorApi:
    return app.state.director_api
