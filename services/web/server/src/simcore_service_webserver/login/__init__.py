""" Login submodule

This submodule is a modification of aiohttp-login

 TODO: create stand-alone fork of aiohttp-login
"""
import logging

import asyncpg
from aiohttp import web

from servicelib.application_keys import APP_CONFIG_KEY, APP_DB_POOL_KEY

from ..db import DSN
from ..db_config import CONFIG_SECTION_NAME as DB_SECTION
from ..email_config import CONFIG_SECTION_NAME as SMTP_SECTION
from ..rest_config import APP_OPENAPI_SPECS_KEY
from ..statics import INDEX_RESOURCE_NAME
from .cfg import APP_LOGIN_CONFIG, cfg
from .routes import create_routes
from .storage import AsyncpgStorage

log = logging.getLogger(__name__)


async def pg_pool(app: web.Application):

    smtp_config = app[APP_CONFIG_KEY][SMTP_SECTION]
    config = {"SMTP_{}".format(k.upper()): v for k, v in smtp_config.items()}
    # TODO: test keys!
    #'SMTP_SENDER': None,
    #'SMTP_HOST': REQUIRED,
    #'SMTP_PORT': REQUIRED,
    #'SMTP_TLS': False,
    #'SMTP_USERNAME': None,
    #'SMTP_PASSWORD': None,

    config = (config or {}).copy()
    config['APP'] = app

    db_config = app[APP_CONFIG_KEY][DB_SECTION]['postgres']
    app[APP_DB_POOL_KEY] = await asyncpg.create_pool(dsn=DSN.format(**db_config), loop=app.loop)

    config["STORAGE"] = AsyncpgStorage(app[APP_DB_POOL_KEY]) #NOTE: this key belongs to cfg, not settings!
    cfg.configure(config)

    if INDEX_RESOURCE_NAME in app.router:
        cfg['LOGIN_REDIRECT'] = app.router[INDEX_RESOURCE_NAME].url_for()
    else:
        log.warning("Unknown location for login page. Defaulting redirection to %s", cfg['LOGIN_REDIRECT'] )

    app[APP_LOGIN_CONFIG] = cfg


def setup(app: web.Application):
    log.debug("Setting up %s ...", __name__)

    # TODO: requires rest ready!
    assert SMTP_SECTION in app[APP_CONFIG_KEY]
    assert DB_SECTION in app[APP_CONFIG_KEY]

    # TODO: automatize dependencies
    enabled = all( app[APP_CONFIG_KEY].get(mod, {}).get("enabled", True) for mod in (SMTP_SECTION, DB_SECTION) )
    if not enabled:
        log.warning("Disabling '%s' since %s or %s were explictily disabled in config", __name__, SMTP_SECTION, DB_SECTION)
        return

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
