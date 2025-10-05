# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from collections.abc import Callable
from pathlib import Path

import pytest
from aiohttp import web
from faker import Faker
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.openapi_specs import Entrypoint
from simcore_service_webserver.application import create_application
from simcore_service_webserver.application_settings import get_application_settings
from simcore_service_webserver.rest._utils import get_openapi_specs_path


@pytest.fixture(scope="session")
def openapi_specs_path(api_version_prefix: str) -> Path:
    # overrides pytest_simcore.openapi_specs.app_openapi_specs_path fixture
    return get_openapi_specs_path(api_version_prefix)


@pytest.fixture
def app_environment(
    mock_env_devel_environment: EnvVarsDict,
    docker_compose_service_environment_dict: EnvVarsDict,
    monkeypatch: pytest.MonkeyPatch,
    faker: Faker,
) -> EnvVarsDict:
    # Needed to enable  WEBSERVER_ACTIVITY using PROMETEUS below
    monkeypatch.delenv("WEBSERVER_ACTIVITY", raising=False)
    docker_compose_service_environment_dict.pop("WEBSERVER_ACTIVITY", None)

    return mock_env_devel_environment | setenvs_from_dict(
        monkeypatch,
        {
            **docker_compose_service_environment_dict,
            # disable bundle configs
            "WEBSERVER_DB_LISTENER": "0",
            "WEBSERVER_GARBAGE_COLLECTOR": "null",
            # enable plugins that by default are disabled
            "WEBSERVER_DEV_FEATURES_ENABLED": "1",
            # enables activity WEBSERVER_ACTIVITY
            "PROMETHEUS_URL": f"https://{faker.domain_name()}",
            "PROMETHEUS_USERNAME": faker.user_name(),
            "PROMETHEUS_PASSWORD": faker.password(),
        },
    )


@pytest.fixture
def app(app_environment: EnvVarsDict) -> web.Application:
    assert app_environment
    # Expects that:
    # - routings happen during setup!
    # - all plugins are setup but app is NOT started (i.e events are not triggered)
    #
    app_ = create_application()
    print(get_application_settings(app_).model_dump_json(indent=1))
    return app_


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
