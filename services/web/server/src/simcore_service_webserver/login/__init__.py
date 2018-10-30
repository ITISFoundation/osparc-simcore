""" Login submodule

This submodule is a modification of aiohttp-login

 TODO: create stand-alone fork of aiohttp-login
"""
import logging

from aiohttp import web

import asyncpg

from ..application_keys import APP_CONFIG_KEY, APP_DB_POOL_KEY
from ..db import DSN
from .cfg import cfg
from .storage import AsyncpgStorage

log = logging.getLogger(__name__)

APP_LOGIN_CONFIG = __name__ + ".config"
CFG_LOGIN_STORAGE = __name__ + ".storage"


async def pg_pool(app: web.Application):

    smtp_config = app[APP_CONFIG_KEY]['smtp']
    config = {"SMTP_{}".format(k.upper()): v for k, v in smtp_config.items()}
    #'SMTP_SENDER': None,
    #'SMTP_HOST': REQUIRED,
    #'SMTP_PORT': REQUIRED,
    #'SMTP_TLS': False,
    #'SMTP_USERNAME': None,
    #'SMTP_PASSWORD': None,

    config['REGISTRATION_CONFIRMATION_REQUIRED'] = True

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
    app.on_startup.append(pg_pool)


def get_storage(app: web.Application):
    return app[APP_LOGIN_CONFIG]['STORAGE']

# alias
setup_login = setup

__all__ = (
    'setup_login',
    'get_storage'
)
