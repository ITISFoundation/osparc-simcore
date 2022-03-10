# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=no-name-in-module

from typing import Dict
from unittest.mock import Mock

import pytest
from servicelib.aiohttp.application_keys import APP_CONFIG_KEY, APP_OPENAPI_SPECS_KEY
from servicelib.aiohttp.application_setup import APP_SETUP_COMPLETED_KEY
from simcore_service_webserver import diagnostics_handlers
from simcore_service_webserver.application_settings import setup_settings
from simcore_service_webserver.diagnostics import setup_diagnostics
from simcore_service_webserver.rest import api_version_prefix


class MockApp(dict):
    middlewares = []
    cleanup_ctx = []
    router = Mock()
    _overriden = []

    def __setitem__(self, key, value):
        if key in self:
            current_value = self.__getitem__(key)
            self._overriden.append((key, value))

            print(f"ERROR app['{key}'] = {current_value} overriden with {value}")

        super().__setitem__(key, value)

    def assert_none_overriden(self):
        assert not self._overriden


@pytest.fixture
def app_mock(openapi_specs):
    app = MockApp()

    # some inits to emulate app setup
    app[APP_CONFIG_KEY] = {
        "diagnostics": {"diagnostics.enabled": True},
    }

    # some inits to emulate simcore_service_webserver.rest setup
    app[APP_SETUP_COMPLETED_KEY] = ["simcore_service_webserver.rest"]
    app[APP_OPENAPI_SPECS_KEY] = openapi_specs

    return app


def test_unique_application_keys(
    app_mock, openapi_specs, mock_env_devel_environment: Dict[str, str]
):
    # this module has A LOT of constants and it is easy to override them
    setup_settings(app_mock)
    setup_diagnostics(app_mock)

    for key, value in app_mock.items():
        print(f"app['{key}'] = {value}")

    assert any(key for key in app_mock if "diagnostics" in key)

    app_mock.assert_none_overriden()


@pytest.mark.parametrize("route", diagnostics_handlers.routes, ids=lambda r: r.path)
def test_route_against_openapi_specs(route, openapi_specs):

    assert route.path.startswith(f"/{api_version_prefix}")
    path = route.path.replace(f"/{api_version_prefix}", "")

    assert (
        openapi_specs.paths[path].operations[route.method.lower()].operation_id
        == route.kwargs["name"]
    ), f"openapi specs does not fit route {route}"
