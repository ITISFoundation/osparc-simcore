from fastapi import Depends, FastAPI
from fastapi.requests import Request

from ...services.director import DirectorApi


def _get_app(request: Request) -> FastAPI:
    return request.app


def get_director_api(
    app: FastAPI = Depends(_get_app),
) -> DirectorApi:
    director: DirectorApi = app.state.director_api
    return director
