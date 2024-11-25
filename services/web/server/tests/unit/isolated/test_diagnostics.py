# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

from unittest.mock import Mock

import pytest
from servicelib.aiohttp.application_setup import APP_SETUP_COMPLETED_KEY
from simcore_service_webserver.application_settings import setup_settings
from simcore_service_webserver.diagnostics.plugin import setup_diagnostics
from simcore_service_webserver.rest.plugin import setup_rest


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

    def add_routes(self, *args, **kwargs):
        self.router.add_routes(*args, **kwargs)


@pytest.fixture
def app_mock():
    app = MockApp()

    # emulates security is initialized
    app[APP_SETUP_COMPLETED_KEY] = ["simcore_service_webserver.security"]

    return app


def test_unique_application_keys(app_mock, mock_env_devel_environment: dict[str, str]):
    setup_settings(app_mock)
    setup_rest(app_mock)
    setup_diagnostics(app_mock)

    for key, value in app_mock.items():
        print(f"app['{key}'] = {value}")

    assert any(key for key in app_mock if "diagnostics" in key)

    # this module has A LOT of constants and it is easy to override them
    app_mock.assert_none_overriden()
