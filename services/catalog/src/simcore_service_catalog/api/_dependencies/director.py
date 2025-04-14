from typing import Annotated

from fastapi import Depends, FastAPI
from servicelib.fastapi.dependencies import get_app

from ...clients.director import DirectorClient


def get_director_client(
    app: Annotated[FastAPI, Depends(get_app)],
) -> DirectorClient:
    director: DirectorClient = app.state.director_api
    return director
