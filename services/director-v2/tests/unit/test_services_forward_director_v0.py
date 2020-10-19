# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=protected-access
import pytest
import respx
from fastapi import FastAPI, status
from simcore_service_director_v2.core.application import init_app
from simcore_service_director_v2.core.settings import AppSettings
from starlette.testclient import TestClient


@pytest.fixture
def minimal_app(loop, project_env_devel_environment) -> FastAPI:

    settings = AppSettings.create_from_env()
    app = init_app(settings)
    return app


@pytest.fixture
def client(minimal_app):
    # NOTE: this way we ensure the events are run in the application
    # since it starts the app on a test server
    with TestClient(
        minimal_app,
        base_url="http://director-v2-test-server",
        raise_server_exceptions=True,
    ) as client:
        yield client


@pytest.fixture
def mocked_director_v0_service_api(minimal_app):
    with respx.mock(
        base_url= minimal_app.state.settings.director_v0.base_url(include_tag=False),
        assert_all_called=False,
        assert_all_mocked=True,
    ) as respx_mock:
        # lists services
        respx_mock.get(
            "/v0/services?service_type=computational",
            content={"data": ["service1", "service2"]},
            alias="list_services",
        )
        yield respx_mock


def test_forward_list_services(client, mocked_director_v0_service_api):
    response = client.get("/v0/services?service_type=computational")

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"data": ["service1", "service2"]}
    assert mocked_director_v0_service_api["list_services"].called
