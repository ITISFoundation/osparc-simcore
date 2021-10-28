# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=protected-access


import asyncio
from typing import Dict, Iterable, Iterator

import pytest
import respx
from _pytest.monkeypatch import MonkeyPatch
from fastapi import FastAPI
from respx.router import MockRouter
from simcore_service_catalog.api.dependencies.director import get_director_api
from simcore_service_catalog.core.application import init_app
from simcore_service_catalog.services.director import DirectorApi
from starlette.testclient import TestClient


@pytest.fixture
def minimal_app(
    monkeypatch: MonkeyPatch, testing_environ_vars: Dict[str, str]
) -> Iterator[FastAPI]:
    # disable a couple of subsystems
    monkeypatch.setenv("CATALOG_POSTGRES", "null")
    monkeypatch.setenv("CATALOG_TRACING", "null")

    app = init_app()

    yield app


@pytest.fixture()
def client(minimal_app: FastAPI) -> Iterable[TestClient]:
    # NOTE: this way we ensure the events are run in the application
    # since it starts the app on a test server
    with TestClient(minimal_app) as client:
        yield client


@pytest.fixture
def mocked_director_service_api(minimal_app: FastAPI) -> MockRouter:
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
    loop: asyncio.AbstractEventLoop,
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
