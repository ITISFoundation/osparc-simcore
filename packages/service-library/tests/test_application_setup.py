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
from servicelib.application_setup import mark_as_module_setup, ModuleCategory

log = logging.getLogger(__name__)


@mark_as_module_setup("foo", ModuleCategory.ADDON, logger=log)
def setup_subsystem_foo(app: web.Application, arg1, kargs=33):
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


def test_setup_decorator(app_config):
    app = web.Application()
    app[APP_CONFIG_KEY] = app_config

    assert setup_subsystem_foo(app, 1)

    assert setup_subsystem_foo.metadata()['module_name'] == 'foo'

    app_config['foo']['enabled'] = False
    assert not setup_subsystem_foo(app, 2)
