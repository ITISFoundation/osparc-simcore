# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=protected-access
import re

import pytest
import respx


@pytest.fixture(autouse=True)
def minimal_director_config(project_env_devel_environment, monkeypatch):
    """set a minimal configuration for testing the director connection only"""
    monkeypatch.setenv("DIRECTOR_V0_ENABLED", "0")
    monkeypatch.setenv("DIRECTOR_V2_POSTGRES_ENABLED", "0")
    monkeypatch.setenv("DIRECTOR_V2_CELERY_ENABLED", "0")
    monkeypatch.setenv("DIRECTOR_V2_DOCKER_REGISTRY_ENABLED", "1")
    monkeypatch.setenv("DIRECTOR_V2_CELERY_SCHEDULER_ENABLED", "0")


@pytest.fixture
def mocked_registry_service_api(minimal_app):
    with respx.mock(
        base_url=str(minimal_app.state.settings.REGISTRY.api_url),
        assert_all_called=False,
        assert_all_mocked=True,
    ) as respx_mock:
        # lists images catalog
        respx_mock.get(re.compile(r"/_catalog\?n=\d+"), name="catalog",).respond(
            json={"repositories": ["/simcore/services/comp/itis/sleeper"]},
        )
        # lists tags of sleeper
        respx_mock.get(
            "/simcore/services/comp/itis/sleeper/tags/list?n=50",
            name="sleeper-tags",
        ).respond(
            json={"tags": ["1.0", "2.0"]},
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
