# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from typing import NamedTuple

import pytest
import simcore_service_storage.application
from aiohttp import web
from faker import Faker
from openapi_core.schema.specs.models import Spec as OpenApiSpecs
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.utils_envs import setenvs_from_dict
from simcore_service_storage.settings import Settings


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
        },
    )


@pytest.fixture
def app(app_environment: EnvVarsDict) -> web.Application:
    # Expects that:
    # - routings happen during setup!
    # - all plugins are setup but app is NOT started (i.e events are not triggered)
    #
    settings = Settings.create_from_envs()
    print(settings.json(indent=1))
    return simcore_service_storage.application.create(settings)


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
                    path=resource_path,
                    name=route.name,
                )
            )
    return entrypoints


def test_named_api_resources_against_openapi_specs(
    expected_openapi_entrypoints: set[Entrypoint],
    app_entrypoints: set[Entrypoint],
):
    # check whether exposed routes implements openapi.json contract

    assert app_entrypoints == expected_openapi_entrypoints

    # NOTE: missing here is:
    # - input schemas (path, query and body)
    # - output schemas (success/error responses and bodies)
    #
