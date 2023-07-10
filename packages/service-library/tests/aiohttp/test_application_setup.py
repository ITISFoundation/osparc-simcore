# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from unittest.mock import Mock

import pytest
from aiohttp import web
from servicelib.aiohttp.application_keys import APP_CONFIG_KEY
from servicelib.aiohttp.application_setup import (
    DependencyError,
    ModuleCategory,
    SkipModuleSetupError,
    app_module_setup,
    is_setup_completed,
)

log = Mock()


@app_module_setup("package.bar", ModuleCategory.ADDON, logger=log)
def setup_bar(app: web.Application, arg1, *, raise_skip: bool = False):
    return True


@app_module_setup("package.foo", ModuleCategory.ADDON, logger=log)
def setup_foo(app: web.Application, arg1, kargs=33, *, raise_skip: bool = False):
    if raise_skip:
        raise SkipModuleSetupError(reason="explicit skip")
    return True


@app_module_setup(
    "package.zee", ModuleCategory.ADDON, config_enabled="main.zee_enabled", logger=log
)
def setup_zee(app: web.Application, arg1, kargs=55):
    return True


@app_module_setup(
    "package.needs_foo",
    ModuleCategory.SYSTEM,
    depends=[
        "package.foo",
    ],
    logger=log,
)
def setup_needs_foo(app: web.Application, arg1, kargs=55):
    return True


@pytest.fixture
def app_config() -> dict:
    return {
        "foo": {"enabled": True},
        "bar": {"enabled": False},
        "main": {"zee_enabled": True},
    }


@pytest.fixture
def app(app_config):
    _app = web.Application()
    _app[APP_CONFIG_KEY] = app_config
    return _app


def test_setup_config_enabled(app_config, app):
    assert setup_zee(app, 1)

    assert setup_zee.metadata()["config_enabled"] == "main.zee_enabled"
    app_config["main"]["zee_enabled"] = False
    assert not setup_zee(app, 2)


def test_setup_dependencies(app_config, app):

    with pytest.raises(DependencyError):
        setup_needs_foo(app, 1)

    assert setup_foo(app, 1)
    assert setup_needs_foo(app, 2)

    assert setup_needs_foo.metadata()["dependencies"] == [
        setup_foo.metadata()["module_name"],
    ]


def test_marked_setup(app_config, app):
    assert setup_foo(app, 1)

    assert setup_foo.metadata()["module_name"] == "package.foo"
    assert is_setup_completed(setup_foo.metadata()["module_name"], app)

    app_config["foo"]["enabled"] = False
    assert not setup_foo(app, 2)


def test_skip_setup(app_config, app):
    try:
        log.reset_mock()

        assert not setup_foo(app, 1, raise_skip=True)

        # FIXME: mock logger
        # assert log.warning.called
        # warn_msg = log.warning.call_args()[0]
        # assert "package.foo" in warn_msg
        # assert "explicit skip" in warn_msg

        assert setup_foo(app, 1)
    finally:
        log.reset_mock()
