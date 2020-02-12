""" webserver's login subsystem


    This sub-package is based on aiohttp-login https://github.com/imbolc/aiohttp-login
"""
import asyncio
import logging

import asyncpg
from aiohttp import web

from servicelib.aiopg_utils import DSN
from servicelib.application_keys import APP_CONFIG_KEY
from servicelib.application_setup import ModuleCategory, app_module_setup

from ..db_config import CONFIG_SECTION_NAME as DB_SECTION
from ..email_config import CONFIG_SECTION_NAME as SMTP_SECTION
from ..rest_config import APP_OPENAPI_SPECS_KEY
from ..rest_config import CONFIG_SECTION_NAME as REST_SECTION
from ..statics import INDEX_RESOURCE_NAME
from .cfg import APP_LOGIN_CONFIG, cfg
from .config import CONFIG_SECTION_NAME
from .routes import create_routes
from .storage import AsyncpgStorage

log = logging.getLogger(__name__)
module_name = __name__.replace(".__init__", "")

TIMEOUT_SECS = 5


async def _setup_config_and_pgpool(app: web.Application):
    """
        - gets input configs from different subsystems and initializes cfg (internal configuration)
        - creates a postgress pool and asyncpg storage object

    :param app: fully setup application on startup
    :type app: web.Application
    """
    login_cfg = app[APP_CONFIG_KEY].get(CONFIG_SECTION_NAME, {}) # optional!
    stmp_cfg = app[APP_CONFIG_KEY][SMTP_SECTION]
    db_cfg = app[APP_CONFIG_KEY][DB_SECTION]['postgres']

    # db
    #TODO: setup lifetime of this pool?
    #TODO: determin min/max size of the pool
    pool = await asyncpg.create_pool(
        dsn=DSN.format(**db_cfg) + f"?application_name={module_name}_{id(app)}",
        min_size=db_cfg['minsize'],
        max_size=db_cfg['maxsize'],
        loop=asyncio.get_event_loop())

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

    yield # ----------------

    if config["STORAGE"].pool is not pool:
        log.error("Somebody has changed the db pool")
    try:
        await asyncio.wait_for(pool.close(), timeout=TIMEOUT_SECS)
    except asyncio.TimeoutError:
        log.exception("Failed to close login storage loop")



@app_module_setup(module_name, ModuleCategory.ADDON,
    depends=[f'simcore_service_webserver.{mod}' for mod in ('rest', 'db') ],
    logger=log)
def setup(app: web.Application):
    """ Setting up subsystem in application

    :param app: main application
    :type app: web.Application
    """
    assert REST_SECTION in app[APP_CONFIG_KEY] # nosec
    assert SMTP_SECTION in app[APP_CONFIG_KEY] # nosec
    assert DB_SECTION in app[APP_CONFIG_KEY]   # nosec

    # TODO: automatize dependencies
    enabled = all( app[APP_CONFIG_KEY].get(mod, {}).get("enabled", True) for mod in (SMTP_SECTION, DB_SECTION) )
    if not enabled:
        log.warning("Disabling '%s' since %s or %s were explictily disabled in config", __name__, SMTP_SECTION, DB_SECTION)
        return False

    # routes
    specs = app[APP_OPENAPI_SPECS_KEY]
    routes = create_routes(specs)
    app.router.add_routes(routes)

    # signals
    app.cleanup_ctx.append(_setup_config_and_pgpool)
    return True


# alias
setup_login = setup

__all__ = (
    'setup_login'
)
