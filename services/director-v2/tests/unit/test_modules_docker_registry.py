# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=protected-access
import re

import pytest
import respx


@pytest.fixture(autouse=True)
def minimal_director_config(monkeypatch):
    """set a minimal configuration for testing the director connection only"""
    monkeypatch.setenv("DIRECTOR_ENABLED", "0")
    monkeypatch.setenv("POSTGRES_ENABLED", "0")
    monkeypatch.setenv("CELERY_ENABLED", "0")
    monkeypatch.setenv("REGISTRY_ENABLED", "1")


@pytest.fixture
def mocked_registry_service_api(minimal_app):
    with respx.mock(
        base_url=str(minimal_app.state.settings.registry.url),
        assert_all_called=False,
        assert_all_mocked=True,
    ) as respx_mock:
        # lists images catalog
        respx_mock.get(
            re.compile(r"/v2/_catalog\?n=\d+"),
            content={"repositories": ["/simcore/services/comp/itis/sleeper"]},
            alias="catalog",
        )
        # lists tags of sleeper
        respx_mock.get(
            "/v2/simcore/services/comp/itis/sleeper/tags/list?n=50",
            content={"tags": ["1.0", "2.0"]},
            alias="sleeper-tags",
        )
        yield respx_mock


async def test_docker_registry_client(minimal_app, mocked_registry_service_api):
    registry_api = minimal_app.state.docker_registry_api

    images_catalog = await registry_api.list_repositories()
    assert images_catalog
    assert mocked_registry_service_api["catalog"].called

    # tags = await registry_api.list_image_tags(image_key="services/comp/itis/sleeper")
    # assert tags == ["1.0", "2.0"]
    # assert mocked_registry_service_api["sleeper-tags"].called
