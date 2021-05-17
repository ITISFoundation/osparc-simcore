# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name


import pytest
import sqlalchemy as sa
from fastapi import FastAPI
from simcore_service_catalog.api.dependencies.director import get_director_api
from simcore_service_catalog.core.application import init_app
from starlette.testclient import TestClient


@pytest.fixture
def app(monkeypatch, service_test_environ, postgres_db: sa.engine.Engine) -> FastAPI:
    app = init_app()
    yield app


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    with TestClient(app) as cli:
        # Note: this way we ensure the events are run in the application
        yield cli


@pytest.fixture()
async def director_mockup(loop, app: FastAPI):
    class FakeDirector:
        async def get(self, url: str):
            return ""

    app.dependency_overrides[get_director_api] = FakeDirector

    yield

    app.dependency_overrides[get_director_api] = None
