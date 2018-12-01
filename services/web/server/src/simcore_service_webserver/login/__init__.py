""" Login submodule

This submodule is a modification of aiohttp-login

 TODO: create stand-alone fork of aiohttp-login
"""
import asyncio
import logging

import asyncpg
from aiohttp import web

from servicelib.application_keys import APP_CONFIG_KEY

from ..db import DSN
from ..db_config import CONFIG_SECTION_NAME as DB_SECTION
from ..email_config import CONFIG_SECTION_NAME as SMTP_SECTION
from ..rest_config import APP_OPENAPI_SPECS_KEY
from ..statics import INDEX_RESOURCE_NAME
from .cfg import APP_LOGIN_CONFIG, cfg
from .config import CONFIG_SECTION_NAME
from .routes import create_routes
from .storage import AsyncpgStorage

log = logging.getLogger(__name__)

TIMEOUT_SECS = 5


async def _cleanup_context(app: web.Application):
    login_cfg = app[APP_CONFIG_KEY].get(CONFIG_SECTION_NAME, {}) # optional!
    stmp_cfg = app[APP_CONFIG_KEY][SMTP_SECTION]
    db_cfg = app[APP_CONFIG_KEY][DB_SECTION]['postgres']

    # db
    pool = await asyncpg.create_pool(dsn=DSN.format(**db_cfg), loop=app.loop)
    storage = AsyncpgStorage(pool) #NOTE: this key belongs to cfg, not settings!

    # config
    config = {}
    for key, value in login_cfg.items():
        config[key.upper()] = value

    for key, value in stmp_cfg.items():
        config["SMTP_{}".format(key.upper())] = value

    config['APP'] = app
    config["STORAGE"] = storage

    cfg.configure(config)

    if INDEX_RESOURCE_NAME in app.router:
        cfg['LOGIN_REDIRECT'] = app.router[INDEX_RESOURCE_NAME].url_for()
    else:
        log.warning("Unknown location for login page. Defaulting redirection to %s",
                        cfg['LOGIN_REDIRECT'] )

    app[APP_LOGIN_CONFIG] = cfg

    yield

    try:
        await asyncio.wait_for( pool.close(), timeout=TIMEOUT_SECS, loop=app.loop)
    except asyncio.TimeoutError:
        log.exception("Failed to close login storage loop")



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
    app.cleanup_ctx.append(_cleanup_context)


# alias
setup_login = setup

__all__ = (
    'setup_login'
)
