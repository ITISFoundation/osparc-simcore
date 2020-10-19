# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=protected-access

import pytest
import respx
from fastapi import FastAPI
from starlette.testclient import TestClient

from simcore_service_director_v2.core.application import init_app
from simcore_service_director_v2.core.settings import AppSettings

@pytest.fixture
def minimal_app(loop, project_env_devel_environment) -> FastAPI:
    settings = AppSettings.create_from_env()
    app = init_app(settings)

    # NOTE: this way we ensure the events are run in the application
    # since it starts the app on a test server
    with TestClient(app):
        yield app


@pytest.fixture
def mocked_registry_service_api(minimal_app):

    with respx.mock(
        base_url=minimal_app.state.settings.registry.url,
        assert_all_called=False,
        assert_all_mocked=True,
    ) as respx_mock:
        # lists images catalog
        respx_mock.get(
            "_catalog",
            content={"repositories": ["/simcore/services/comp/itis/sleeper"]},
            alias="catalog",
        )
        # lists tags of sleeper
        respx_mock.get(
            "/simcore/services/comp/itis/sleeper/tags/list?n=50",
            content={"tags": ["1.0", "2.0"]},
            alias="sleeper-tags",
        )
        yield respx_mock


async def test_docker_registry_client(minimal_app, mocked_registry_service_api):
    registry_api = minimal_app.state.docker_registry_api

    images_catalog = await registry_api.list_repositories()
    assert images_catalog
    assert mocked_registry_service_api["catalog"].called

    tags = await registry_api.list_image_tags(image_key="services/comp/itis/sleeper")
    assert tags == ["1.0", "2.0"]
    assert mocked_registry_service_api["sleeper-tags"].called
