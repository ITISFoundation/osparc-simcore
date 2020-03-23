# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import logging
from typing import Dict

import pytest
from aiohttp import web

from servicelib.application_keys import APP_CONFIG_KEY
from servicelib.application_setup import (
    APP_SETUP_KEY,
    DependencyError,
    ModuleCategory,
    app_module_setup,
)

log = logging.getLogger(__name__)


@app_module_setup("package.bar", ModuleCategory.ADDON, logger=log)
def setup_bar(app: web.Application, arg1, kargs=55):
    return True


@app_module_setup("package.foo", ModuleCategory.ADDON, logger=log)
def setup_foo(app: web.Application, arg1, kargs=33):
    return True


@app_module_setup(
    "package.zee", ModuleCategory.ADDON, config_enabled="main.zee_enabled", logger=log
)
def setup_zee(app: web.Application, arg1, kargs=55):
    return True


@app_module_setup(
    "package.needs_foo", ModuleCategory.SYSTEM, depends=["package.foo",], logger=log
)
def setup_needs_foo(app: web.Application, arg1, kargs=55):
    return True


@pytest.fixture
def app_config() -> Dict:
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
    assert setup_foo.metadata()["module_name"] in app[APP_SETUP_KEY]

    app_config["foo"]["enabled"] = False
    assert not setup_foo(app, 2)
