# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=protected-access


from typing import Iterator

import pytest
import respx
from fastapi import FastAPI
from simcore_service_catalog.api.dependencies.director import get_director_api
from simcore_service_catalog.core.application import init_app
from simcore_service_catalog.core.settings import (
    AppSettings,
    ClientRequestSettings,
    DirectorSettings,
    PGSettings,
)
from simcore_service_catalog.services.director import DirectorApi
from starlette.testclient import TestClient


@pytest.fixture
def minimal_app(loop, testing_environ_vars) -> Iterator[FastAPI]:
    # TODO: auto generate fakes

    # avoid init of pg or director API clients
    settings = AppSettings(
        postgres=PGSettings(enabled=False),
        director=DirectorSettings(enabled=False),
        client_request=ClientRequestSettings(),
    )
    app = init_app(settings)

    # NOTE: this way we ensure the events are run in the application
    # since it starts the app on a test server
    with TestClient(app):
        yield app


@pytest.fixture
def mocked_director_service_api(minimal_app):
    with respx.mock(
        base_url=minimal_app.state.settings.director.base_url,
        assert_all_called=False,
        assert_all_mocked=True,
    ) as respx_mock:
        respx_mock.get("/services", name="list_services").respond(
            200, json={"data": ["one", "two"]}
        )

        yield respx_mock


async def test_director_client_setup(minimal_app, mocked_director_service_api):

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


# async def test_resilience_to_failing_director_service(
#    minimal_app, mocked_director_service_api
# ):
#    pass
