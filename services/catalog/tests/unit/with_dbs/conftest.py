# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import sys
from pathlib import Path
from typing import Dict

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from simcore_service_catalog.core.application import init_app

current_dir = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent


@pytest.fixture(scope="session")
def test_docker_compose_file() -> Path:
    # OVERRIDES pytest_simcore.postgres_service2.test_docker_compose_file
    return current_dir / "docker-compose.yml"


@pytest.fixture
def app(
    monkeypatch,
    test_environment: Dict[str, str],  # pytest_simcore.postgres_service2
    apply_migration,  # pytest_simcore.postgres_service2
) -> FastAPI:

    # Emulates environ so settings can get config
    for key, value in test_environment.items():
        monkeypatch.setenv(key, value)

    app = init_app()
    yield app


@pytest.fixture
def client(app) -> TestClient:
    with TestClient(app) as cli:
        # Note: this way we ensure the events are run in the application
        yield cli
