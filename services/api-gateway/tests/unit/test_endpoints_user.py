# pylint: disable=unused-variable
# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name

from typing import Dict

import pytest
from aiopg.sa.engine import Engine, create_engine
from starlette import status
from starlette.testclient import TestClient

from simcore_service_api_gateway import application
from simcore_service_api_gateway.__version__ import api_version, api_vtag
from simcore_service_api_gateway.settings import AppSettings
from simcore_service_api_gateway.main import build_app


@pytest.fixture(scope="module")
async def postgres_service(monkeypatch) -> Engine:
    # test environs
    monkeypatch.setenv("POSTGRES_USER", "test")
    monkeypatch.setenv("POSTGRES_PASSWORD", "test")
    monkeypatch.setenv("POSTGRES_DB", "test")

    # TODO: start pg db and return an engine
    async with create_engine() as engine:
        yield engine


@pytest.fixture(scope="module")
async def user_in_db(postgres_service):
    user = {}
    return user


@pytest.fixture(scope="module")
async def api_keys_in_db(postgres_service):
    api_keys = {"key": "key", "secret": "secret"}
    # TODO: inject api-keys in db
    return api_keys


@pytest.fixture
def client(monkeypatch, postgres_service) -> TestClient:
    # test environs
    monkeypatch.setenv("LOGLEVEL", "debug")
    monkeypatch.setenv("SC_BOOT_MODE", "production")

    app = build_app()

    # test client:
    # Context manager to trigger events: https://fastapi.tiangolo.com/advanced/testing-events/
    with TestClient(app) as cli:
        yield cli


def test_get_user(client: TestClient, api_keys_in_db: Dict, user_in_db: Dict):
    response = client.get("f"/{api_vtag}/meta")
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["version"] == api_version

    # TODO: https://requests-oauthlib.readthedocs.io/en/latest/oauth2_workflow.html#backend-application-flow

    # TODO: authenciate with API
    auth_data = {
        "grant_type": "password",
        "scope": "me projects you".split(),
        "username": api_keys_in_db["key"],
        "password": api_keys_in_db["secret"],
    }

    # TODO: application/x-www-form-urlencoded
    response = client.post(f"/{api_vtag}/token", **auth_data)
    # json response
    assert response.json() == {"access_token": "string", "token_type": "string"}

    # TODO: add access token in header??
    response = client.get(f"/{api_vtag}/user")
    assert response.status_code == status.HTTP_200_OK

    assert response.json() == {"name": user_in_db["name"], "email": user_in_db["email"]}

    ## response = client.get(f"/{api_vtag}/studies")
