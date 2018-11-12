""" Login submodule

This submodule is a modification of aiohttp-login

 TODO: create stand-alone fork of aiohttp-login
"""
import logging

import asyncpg
from aiohttp import web

from ..application_keys import APP_CONFIG_KEY, APP_DB_POOL_KEY
from ..db import DSN
from ..email_config import CONFIG_SECTION_NAME as CONFIG_STMP_SECTION
from ..rest_config import APP_OPENAPI_SPECS_KEY
from .cfg import cfg, APP_LOGIN_CONFIG
from .storage import AsyncpgStorage
from .routes import create_routes

log = logging.getLogger(__name__)


async def pg_pool(app: web.Application):
    smtp_config = app[APP_CONFIG_KEY][CONFIG_STMP_SECTION]
    config = {"SMTP_{}".format(k.upper()): v for k, v in smtp_config.items()}
    #'SMTP_SENDER': None,
    #'SMTP_HOST': REQUIRED,
    #'SMTP_PORT': REQUIRED,
    #'SMTP_TLS': False,
    #'SMTP_USERNAME': None,
    #'SMTP_PASSWORD': None,

    config = (config or {}).copy()
    config['APP'] = app

    db_config = app[APP_CONFIG_KEY]['postgres']
    app[APP_DB_POOL_KEY] = await asyncpg.create_pool(dsn=DSN.format(**db_config), loop=app.loop)

    # FIXME: replace by CFG_LOGIN_STORAGE
    config['STORAGE'] = AsyncpgStorage(app[APP_DB_POOL_KEY])
    cfg.configure(config)

    app[APP_LOGIN_CONFIG] = cfg


def setup(app: web.Application):
    log.debug("Setting up %s ...", __name__)

    # TODO: requires rest ready!
    assert CONFIG_STMP_SECTION in app[APP_CONFIG_KEY]

    # routes
    specs = app[APP_OPENAPI_SPECS_KEY]
    routes = create_routes(specs)
    app.router.add_routes(routes)

    # signals
    app.on_startup.append(pg_pool)


# alias
setup_login = setup

__all__ = (
    'setup_login'
)
