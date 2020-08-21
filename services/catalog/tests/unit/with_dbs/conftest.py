# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import sys
from pathlib import Path
from typing import Dict

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from fastapi import FastAPI
from simcore_service_catalog.api.dependencies.director import get_director_session
from simcore_service_catalog.core.application import init_app
from starlette.testclient import TestClient

current_dir = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent


@pytest.fixture
def app(
    monkeypatch, devel_environ: Dict[str, str], postgres_db: sa.engine.Engine
) -> FastAPI:
    # Emulates environ so settings can get config
    for key, value in devel_environ.items():
        monkeypatch.setenv(key, value)

    app = init_app()
    yield app


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    with TestClient(app) as cli:
        # Note: this way we ensure the events are run in the application
        yield cli


@pytest.fixture()
async def director_mockup(loop, monkeypatch, app: FastAPI):
    class FakeDirector:
        async def get(self, url: str):
            return ""

    app.dependency_overrides[get_director_session] = FakeDirector

    yield

    app.dependency_overrides[get_director_session] = None
