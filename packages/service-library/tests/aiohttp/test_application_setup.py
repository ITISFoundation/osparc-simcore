# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import logging

import pytest
from aiohttp import web
from pytest_mock import MockerFixture, MockType
from servicelib.aiohttp.application_keys import APP_CONFIG_KEY
from servicelib.aiohttp.application_setup import (
    DependencyError,
    ModuleCategory,
    SkipModuleSetupError,
    app_module_setup,
    ensure_single_setup,
    is_setup_completed,
)


@pytest.fixture
def mock_logger(mocker: MockerFixture) -> MockType:
    logger_mock: MockType = mocker.create_autospec(logging.Logger, instance=True)
    return logger_mock


@pytest.fixture
def app_config() -> dict:
    return {
        "foo": {"enabled": True},
        "bar": {"enabled": False},
        "main": {"zee_enabled": True},
    }


@pytest.fixture
def app(app_config: dict) -> web.Application:
    _app = web.Application()
    _app[APP_CONFIG_KEY] = app_config
    return _app


def test_setup_config_enabled(app_config: dict, app: web.Application):

    @app_module_setup(
        "package.zee",
        ModuleCategory.ADDON,
        # legacy support for config_enabled
        config_enabled="main.zee_enabled",
    )
    def setup_zee(app: web.Application, arg) -> bool:
        assert arg
        return True

    assert setup_zee(app, 1)

    assert setup_zee.metadata()["config_enabled"] == "main.zee_enabled"
    app_config["main"]["zee_enabled"] = False

    assert not setup_zee(app, 2)


def test_setup_dependencies(app: web.Application):

    @app_module_setup("package.foo", ModuleCategory.ADDON)
    def setup_foo(app: web.Application) -> bool:
        return True

    @app_module_setup(
        "package.needs_foo",
        ModuleCategory.SYSTEM,
        depends=[
            # This module needs foo to be setup first
            "package.foo",
        ],
    )
    def setup_needs_foo(app: web.Application) -> bool:
        return True

    # setup_foo is not called yet
    with pytest.raises(DependencyError):
        setup_needs_foo(app)

    # ok
    assert setup_foo(app)
    assert setup_needs_foo(app)

    # meta
    assert setup_needs_foo.metadata()["dependencies"] == [
        setup_foo.metadata()["module_name"],
    ]


def test_marked_setup(app_config: dict, app: web.Application):
    @app_module_setup("package.foo", ModuleCategory.ADDON)
    def setup_foo(app: web.Application) -> bool:
        return True

    assert setup_foo(app)
    assert setup_foo.metadata()["module_name"] == "package.foo"
    assert is_setup_completed(setup_foo.metadata()["module_name"], app)

    app_config["foo"]["enabled"] = False
    assert not setup_foo(app)


def test_skip_setup(app: web.Application, mock_logger: MockType):
    @app_module_setup("package.foo", ModuleCategory.ADDON, logger=mock_logger)
    def setup_foo(app: web.Application, *, raise_skip: bool = False) -> bool:
        if raise_skip:
            raise SkipModuleSetupError(reason="explicit skip")
        return True

    assert not setup_foo(app, raise_skip=True)
    assert setup_foo(app)

    assert mock_logger.info.called
    args = [call.args[-1] for call in mock_logger.info.mock_calls]
    assert any("explicit skip" in arg for arg in args)


def setup_basic(app: web.Application) -> bool:
    return True


def setup_that_raises(app: web.Application) -> bool:
    error_msg = "Setup failed"
    raise ValueError(error_msg)


def test_ensure_single_setup_runs_once(app: web.Application, mock_logger: MockType):
    decorated = ensure_single_setup("test.module", logger=mock_logger)(setup_basic)

    # First call succeeds
    assert decorated(app)
    assert is_setup_completed("test.module", app)

    # Second call skips
    assert not decorated(app)


def test_ensure_single_setup_error_handling(
    app: web.Application, mock_logger: MockType
):
    decorated = ensure_single_setup("test.error", logger=mock_logger)(setup_that_raises)

    with pytest.raises(ValueError, match="Setup failed"):
        decorated(app)
    assert not is_setup_completed("test.error", app)


def test_ensure_single_setup_multiple_modules(
    app: web.Application, mock_logger: MockType
):
    decorated1 = ensure_single_setup("module1", logger=mock_logger)(setup_basic)
    decorated2 = ensure_single_setup("module2", logger=mock_logger)(setup_basic)

    assert decorated1(app)
    assert decorated2(app)
    assert is_setup_completed("module1", app)
    assert is_setup_completed("module2", app)
