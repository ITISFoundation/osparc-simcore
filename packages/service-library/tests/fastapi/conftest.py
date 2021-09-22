# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from datetime import datetime

import pytest
from fastapi import FastAPI
from fastapi.routing import APIRouter


@pytest.fixture
def app() -> FastAPI:

    api_router = APIRouter()

    @api_router.get("/")
    def root():
        return {"name": __name__, "timestamp": datetime.utcnow().isoformat()}

    _app = FastAPI()
    _app.include_router(api_router)

    return _app
