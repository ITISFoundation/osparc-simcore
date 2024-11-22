# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from collections.abc import Callable
from pathlib import Path

import pytest
import simcore_service_storage.application
from aiohttp import web
from faker import Faker
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.openapi_specs import Entrypoint
from simcore_service_storage._meta import API_VTAG
from simcore_service_storage.resources import storage_resources
from simcore_service_storage.settings import Settings


@pytest.fixture(scope="session")
def openapi_specs_path() -> Path:
    # overrides pytest_simcore.openapi_specs.app_openapi_specs_path fixture
    spec_path: Path = storage_resources.get_path(f"api/{API_VTAG}/openapi.yaml")
    return spec_path


@pytest.fixture
def app_environment(
    mock_env_devel_environment: EnvVarsDict,
    monkeypatch: pytest.MonkeyPatch,
    faker: Faker,
) -> EnvVarsDict:
    return mock_env_devel_environment | setenvs_from_dict(
        monkeypatch,
        {
            # disable index and statics routings
            "WEBSERVER_STATICWEB": "null",
        },
    )


@pytest.fixture
def app(app_environment: EnvVarsDict) -> web.Application:
    assert app_environment
    # Expects that:
    # - routings happen during setup!
    # - all plugins are setup but app is NOT started (i.e events are not triggered)
    #
    settings = Settings.create_from_envs()
    return simcore_service_storage.application.create(settings)


@pytest.fixture
def app_rest_entrypoints(
    app: web.Application,
    create_aiohttp_app_rest_entrypoints: Callable[[web.Application], set[Entrypoint]],
) -> set[Entrypoint]:
    # check whether exposed routes implements openapi.json contract
    return create_aiohttp_app_rest_entrypoints(app)


def test_app_named_resources_against_openapi_specs(
    openapi_specs_entrypoints: set[Entrypoint],
    app_rest_entrypoints: set[Entrypoint],
):
    assert app_rest_entrypoints == openapi_specs_entrypoints

    # NOTE: missing here is:
    # - input schemas (path, query and body)
    # - output schemas (success/error responses and bodies)
    #
