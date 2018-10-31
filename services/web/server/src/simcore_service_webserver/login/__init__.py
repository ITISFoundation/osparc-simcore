""" Login submodule

This submodule is a modification of aiohttp-login

 TODO: create stand-alone fork of aiohttp-login
"""
import logging

import asyncpg
from aiohttp import web

from . import routes as login_routes
from ..application_keys import (APP_CONFIG_KEY, APP_DB_POOL_KEY,
                                APP_OPENAPI_SPECS_KEY)
from ..db import DSN # TODO: get_db_config
from .cfg import cfg
from .settings import APP_LOGIN_CONFIG, CFG_LOGIN_STORAGE, get_storage
from .storage import AsyncpgStorage

log = logging.getLogger(__name__)


async def pg_pool(app: web.Application):

    smtp_config = app[APP_CONFIG_KEY]['smtp']
    config = {"SMTP_{}".format(k.upper()): v for k, v in smtp_config.items()}
    # TODO: test keys!
    #'SMTP_SENDER': None,
    #'SMTP_HOST': REQUIRED,
    #'SMTP_PORT': REQUIRED,
    #'SMTP_TLS': False,
    #'SMTP_USERNAME': None,
    #'SMTP_PASSWORD': None,

    config['REGISTRATION_CONFIRMATION_REQUIRED'] = True

    config = (config or {}).copy()
    config['APP'] = app

    # TODO: guarantee set/getters
    db_config = app[APP_CONFIG_KEY]['postgres']
    app[APP_DB_POOL_KEY] = await asyncpg.create_pool(dsn=DSN.format(**db_config), loop=app.loop)

    config[CFG_LOGIN_STORAGE] = AsyncpgStorage(app[APP_DB_POOL_KEY]) #NOTE: this key belongs to cfg, not settings!
    cfg.configure(config)

    app[APP_LOGIN_CONFIG] = cfg


def setup(app: web.Application):
    log.debug("Setting up %s ...", __name__)

    specs = app[APP_OPENAPI_SPECS_KEY] # validated openapi specs

    routes = login_routes.create(specs)
    app.router.add_routes(routes)

    app.on_startup.append(pg_pool)



# alias
setup_login = setup

__all__ = (
    'setup_login',
    'get_storage'
)
