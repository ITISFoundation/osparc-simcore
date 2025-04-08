from typing import Annotated

from fastapi import Depends, FastAPI
from servicelib.fastapi.dependencies import get_app

from ...services.director import DirectorApi


def get_director_api(
    app: Annotated[FastAPI, Depends(get_app)],
) -> DirectorApi:
    director: DirectorApi = app.state.director_api
    return director
