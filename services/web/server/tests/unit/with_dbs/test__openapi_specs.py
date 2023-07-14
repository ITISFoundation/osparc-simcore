# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from typing import NamedTuple

import pytest
from aiohttp import web
from faker import Faker
from openapi_core.schema.specs.models import Spec as OpenApiSpecs
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.utils_envs import setenvs_from_dict
from simcore_service_webserver._meta import API_VTAG as VX
from simcore_service_webserver.application import create_application
from simcore_service_webserver.application_settings import get_settings


class Entrypoint(NamedTuple):
    name: str
    method: str
    path: str


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
            # disable bundle configs
            "WEBSERVER_DB_LISTENER": "0",
            "WEBSERVER_GARBAGE_COLLECTOR": "null",
            # enable plugins that by default are disabled
            "WEBSERVER_DEV_FEATURES_ENABLED": "1",
            "WEBSERVER_VERSION_CONTROL": "1",
            "WEBSERVER_META_MODELING": "1",
            "WEBSERVER_CLUSTERS": "1",
            # enables activity ACTIVITY
            "PROMETHEUS_URL": f"https://{faker.domain_name()}",
            "PROMETHEUS_USERNAME": faker.user_name(),
            "PROMETHEUS_PASSWORD": faker.password(),
        },
    )


@pytest.fixture
def app(app_environment: EnvVarsDict) -> web.Application:
    # Expects that:
    # - routings happen during setup!
    # - all plugins are setup but app is NOT started (i.e events are not triggered)
    #
    app_ = create_application()
    print(get_settings(app_).json(indent=1))
    return app_


@pytest.fixture
def expected_openapi_entrypoints(openapi_specs: OpenApiSpecs) -> set[Entrypoint]:
    entrypoints: set[Entrypoint] = set()

    # openapi-specifications, i.e. "contract"
    for path, path_obj in openapi_specs.paths.items():
        for operation, operation_obj in path_obj.operations.items():
            entrypoints.add(
                Entrypoint(
                    method=operation.upper(),
                    path=path,
                    name=operation_obj.operation_id,
                )
            )
    return entrypoints


@pytest.fixture
def app_entrypoints(app: web.Application) -> set[Entrypoint]:
    entrypoints: set[Entrypoint] = set()

    # app routes, i.e. "exposed"
    for resource_name, resource in app.router.named_resources().items():
        resource_path = resource.canonical
        for route in resource:
            assert route.name == resource_name
            assert route.resource
            assert route.name is not None

            if route.method == "HEAD":
                continue

            entrypoints.add(
                Entrypoint(
                    method=route.method,
                    path=resource_path.removeprefix(f"/{VX}"),
                    name=route.name,
                )
            )
    return entrypoints


def test_app_named_resources_against_openapi_specs(
    expected_openapi_entrypoints: set[Entrypoint],
    app_entrypoints: set[Entrypoint],
):
    # check whether exposed routes implements openapi.json contract

    assert app_entrypoints == expected_openapi_entrypoints

    # NOTE: missing here is:
    # - input schemas (path, query and body)
    # - output schemas (success/error responses and bodies)
    #
