# pylint:disable=wildcard-import
# pylint:disable=unused-import
# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
import functools
import logging
from typing import Dict, List, Optional

import pytest
from aiohttp import web

from servicelib.application_keys import APP_CONFIG_KEY
from servicelib.application_setup import mark_as_module_setup, ModuleCategory, DependencyError

log = logging.getLogger(__name__)


@mark_as_module_setup("package.bar", ModuleCategory.ADDON, logger=log)
def setup_bar(app: web.Application, arg1, kargs=55):
    return True

@mark_as_module_setup("package.foo", ModuleCategory.ADDON, logger=log)
def setup_foo(app: web.Application, arg1, kargs=33):
    return True

@mark_as_module_setup("package.needs_foo", ModuleCategory.SYSTEM,
    depends=['package.foo',], logger=log)
def setup_needs_foo(app: web.Application, arg1, kargs=55):
    return True


@pytest.fixture
def app_config() -> Dict:
    return {
        'foo': {
            "enabled": True
        },
        'bar': {
            "enabled": False
        }
    }


def test_setup_dependencies(app_config):
    app = web.Application()
    app[APP_CONFIG_KEY] = app_config

    with pytest.raises(DependencyError):
        setup_needs_foo(app, 1)

    assert setup_foo(app, 1)
    assert setup_needs_foo(app, 2)

    assert setup_needs_foo.metadata()['dependencies'] == [setup_foo.metadata()['module_name'], ]


def test_setup_decorator(app_config):
    app = web.Application()
    app[APP_CONFIG_KEY] = app_config

    assert setup_foo(app, 1)

    assert setup_foo.metadata()['module_name'] == 'package.foo'

    app_config['foo']['enabled'] = False
    assert not setup_foo(app, 2)
