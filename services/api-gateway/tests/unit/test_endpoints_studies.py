# pylint: disable=unused-variable
# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name

import pytest
from starlette.testclient import TestClient
from starlette import status

from simcore_service_api_gateway import application, endpoints_check
from simcore_service_api_gateway.__version__ import api_version, api_vtag
from simcore_service_api_gateway.settings import AppSettings


@pytest.fixture
def client(monkeypatch) -> TestClient:
    monkeypatch.setenv("POSTGRES_USER", "test")
    monkeypatch.setenv("POSTGRES_PASSWORD", "test")
    monkeypatch.setenv("POSTGRES_DB", "test")
    monkeypatch.setenv("LOGLEVEL", "debug")
    monkeypatch.setenv("SC_BOOT_MODE", "production")

    # app
    test_settings = AppSettings()
    app = application.create(settings=test_settings)

    # routes
    app.include_router(endpoints_check.router, tags=["check"])

    # test client:
    # Context manager to trigger events: https://fastapi.tiangolo.com/advanced/testing-events/
    with TestClient(app) as cli:
        yield cli


def test_studies_workflow(client: TestClient):

    response = client.get("/meta")
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["version"] == api_version

    # TODO: https://requests-oauthlib.readthedocs.io/en/latest/oauth2_workflow.html#backend-application-flow

    # TODO: authenciate with API
    auth_data = {
        "grant_type": "password",
        "scope": "me projects you".split(),
        "username": api_key,
        "password": api_secret,
    }

    response = client.post(
        f"/{api_vtag}/token", grant_type="", username=api_key, password="",
    )

    access_token = response.json()

    # add in header -------??

    response = client.get(f"/{api_vtag}/user")
    assert response.status_code == status.HTTP_200_OK
    profile = response.json()
    assert profile == my_profile

    response = client.get(f"/{api_vtag}/studies")
