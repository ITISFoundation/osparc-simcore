# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=no-name-in-module

from typing import Dict
from unittest.mock import Mock

import pytest

from servicelib.application_keys import APP_CONFIG_KEY, APP_OPENAPI_SPECS_KEY
from servicelib.application_setup import APP_SETUP_KEY
from simcore_service_webserver.diagnostics import setup_diagnostics
from simcore_service_webserver.rest import get_openapi_specs_path, load_openapi_specs


class App(dict):
    middlewares = []
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
def openapi_specs(api_version_prefix) -> Dict:
    spec_path = get_openapi_specs_path(api_version_prefix)
    return load_openapi_specs(spec_path)


@pytest.fixture
def app_mock(openapi_specs):
    app = App()

    # some inits to emulate app setup
    app[APP_CONFIG_KEY] = {
        "diagnostics": {"diagnostics.enabled": True},
    }

    # some inits to emulate simcore_service_webserver.rest setup
    app[APP_SETUP_KEY] = ["simcore_service_webserver.rest"]
    app[APP_OPENAPI_SPECS_KEY] = openapi_specs

    return app


def test_unique_application_keys(app_mock, openapi_specs):
    # this module has A LOT of constants and it is easy to override them

    setup_diagnostics(app_mock)

    for key, value in app_mock.items():
        print(f"app['{key}'] = {value}")

    assert any(key for key in app_mock if "diagnostics" in key)

    app_mock.assert_none_overriden()
