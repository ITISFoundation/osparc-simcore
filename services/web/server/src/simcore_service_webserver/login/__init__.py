""" webserver's login subsystem


    This sub-package is based on aiohttp-login https://github.com/imbolc/aiohttp-login
"""
import asyncio
import logging
from typing import Dict

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


TIMEOUT_SECS = 5


def _create_login_config(app: web.Application, storage: AsyncpgStorage) -> Dict:
    """
        Creates compatible config to update login.cfg.cfg object
    """
    login_cfg = app[APP_CONFIG_KEY].get(CONFIG_SECTION_NAME, {})  # optional!
    smtp_cfg = app[APP_CONFIG_KEY][SMTP_SECTION]

    config = {"APP": app, "STORAGE": storage}

    def _fmt(val):
        if isinstance(val, str):
            if val.strip().lower() in ["null", "none", ""]:
                return None
        return val

    for key, value in login_cfg.items():
        config[key.upper()] = _fmt(value)

    for key, value in smtp_cfg.items():
        config["SMTP_{}".format(key.upper())] = _fmt(value)

    return config


async def _setup_config_and_pgpool(app: web.Application):
    """
        - gets input configs from different subsystems and initializes cfg (internal configuration)
        - creates a postgress pool and asyncpg storage object

    :param app: fully setup application on startup
    :type app: web.Application
    """
    db_cfg = app[APP_CONFIG_KEY][DB_SECTION]["postgres"]

    # db
    pool = await asyncpg.create_pool(
        dsn=DSN.format(**db_cfg) + f"?application_name={__name__}_{id(app)}",
        min_size=db_cfg["minsize"],
        max_size=db_cfg["maxsize"],
        loop=asyncio.get_event_loop(),
    )

    storage = AsyncpgStorage(pool)  # NOTE: this key belongs to cfg, not settings!

    # config
    config = _create_login_config(app, storage)
    cfg.configure(config)

    if INDEX_RESOURCE_NAME in app.router:
        cfg["LOGIN_REDIRECT"] = app.router[INDEX_RESOURCE_NAME].url_for()
    else:
        log.warning(
            "Unknown location for login page. Defaulting redirection to %s",
            cfg["LOGIN_REDIRECT"],
        )

    app[APP_LOGIN_CONFIG] = cfg

    yield  # ----------------

    if config["STORAGE"].pool is not pool:
        log.error("Somebody has changed the db pool")
    try:
        await asyncio.wait_for(pool.close(), timeout=TIMEOUT_SECS)
    except asyncio.TimeoutError:
        log.exception("Failed to close login storage loop")


@app_module_setup(
    __name__,
    ModuleCategory.ADDON,
    depends=[f"simcore_service_webserver.{mod}" for mod in ("rest", "db")],
    logger=log,
)
def setup_login(app: web.Application):
    """ Setting up login subsystem in application

    """
    # routes
    specs = app[APP_OPENAPI_SPECS_KEY]
    routes = create_routes(specs)
    app.router.add_routes(routes)

    # signals
    app.cleanup_ctx.append(_setup_config_and_pgpool)
    return True


__all__ = "setup_login"
