# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from datetime import datetime

import pytest
from fastapi import FastAPI
from fastapi.params import Query
from fastapi.routing import APIRouter
from pydantic.types import PositiveFloat


@pytest.fixture
def app() -> FastAPI:

    api_router = APIRouter()

    @api_router.get("/")
    def _get_root():
        return {"name": __name__, "timestamp": datetime.utcnow().isoformat()}

    @api_router.get("/data")
    def _get_data(x: PositiveFloat, y: int = Query(..., gt=3, lt=4)):
        pass

    _app = FastAPI()
    _app.include_router(api_router)

    return _app
