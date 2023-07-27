# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=protected-access
# pylint:disable=not-context-manager


from typing import Iterator

import pytest
import respx
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pytest_simcore.helpers.typing_env import EnvVarsDict
from respx.router import MockRouter
from simcore_service_catalog.api.dependencies.director import get_director_api
from simcore_service_catalog.core.application import init_app
from simcore_service_catalog.services.director import DirectorApi


@pytest.fixture
def minimal_app(
    monkeypatch: pytest.MonkeyPatch, service_test_environ: EnvVarsDict
) -> Iterator[FastAPI]:
    # disable a couple of subsystems
    monkeypatch.setenv("CATALOG_POSTGRES", "null")
    monkeypatch.setenv("SC_BOOT_MODE", "local-development")

    app = init_app()

    yield app


@pytest.fixture()
def client(minimal_app: FastAPI) -> Iterator[TestClient]:
    # NOTE: this way we ensure the events are run in the application
    # since it starts the app on a test server
    with TestClient(minimal_app) as client:
        yield client


@pytest.fixture
def mocked_director_service_api(minimal_app: FastAPI) -> Iterator[MockRouter]:
    with respx.mock(
        base_url=minimal_app.state.settings.CATALOG_DIRECTOR.base_url,
        assert_all_called=False,
        assert_all_mocked=True,
    ) as respx_mock:
        respx_mock.head("/", name="healthcheck").respond(200, json={"health": "OK"})
        respx_mock.get("/services", name="list_services").respond(
            200, json={"data": ["one", "two"]}
        )

        yield respx_mock


async def test_director_client_setup(
    mocked_director_service_api: MockRouter,
    minimal_app: FastAPI,
    client: TestClient,
):
    # gets director client as used in handlers
    director_api = get_director_api(minimal_app)

    assert minimal_app.state.director_api == director_api
    assert isinstance(director_api, DirectorApi)

    # use it
    data = await director_api.get("/services")

    # director entry-point has hit
    assert mocked_director_service_api["list_services"].called

    # returns un-enveloped response
    assert data == ["one", "two"]
