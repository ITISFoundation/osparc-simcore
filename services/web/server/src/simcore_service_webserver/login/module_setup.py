import asyncio
import logging
from typing import Dict

import asyncpg
from aiohttp import web
from servicelib.aiohttp.application_keys import APP_CONFIG_KEY, APP_SETTINGS_KEY
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup

from .._constants import APP_OPENAPI_SPECS_KEY, INDEX_RESOURCE_NAME
from ..db_config import CONFIG_SECTION_NAME as DB_SECTION
from ..db_settings import PostgresSettings
from .cfg import APP_LOGIN_CONFIG, cfg
from .cfg_utils import create_login_internal_config
from .routes import create_routes
from .settings import LoginSettings
from .storage import AsyncpgStorage

log = logging.getLogger(__name__)


MAX_TIME_TO_CLOSE_POOL_SECS = 5


async def _setup_config_and_pgpool(app: web.Application):
    """
        - gets input configs from different subsystems and initializes cfg (internal configuration)
        - creates a postgress pool and asyncpg storage object

    :param app: fully setup application on startup
    :type app: web.Application
    """
    db_cfg: Dict = app[APP_CONFIG_KEY][DB_SECTION]["postgres"]
    pg_settings: PostgresSettings = app[APP_SETTINGS_KEY].WEBSERVER_POSTGRES

    # db
    pool: asyncpg.pool.Pool = await asyncpg.create_pool(
        dsn=pg_settings.dsn_with_query,
        min_size=pg_settings.POSTGRES_MINSIZE,
        max_size=pg_settings.POSTGRES_MAXSIZE,
        loop=asyncio.get_event_loop(),
    )  # type: ignore

    storage = AsyncpgStorage(pool)  # NOTE: this key belongs to cfg, not settings!

    # config
    config = create_login_internal_config(app, storage)
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
        await asyncio.wait_for(pool.close(), timeout=MAX_TIME_TO_CLOSE_POOL_SECS)
    except asyncio.TimeoutError:
        log.exception("Failed to close login storage loop")


@app_module_setup(
    "simcore_service_webserver.login",
    ModuleCategory.SYSTEM,
    config_section="WEBSERVER_LOGIN",
    depends=["simcore_service_webserver.rest", "simcore_service_webserver.db"],
    logger=log,
)
def setup_login(app: web.Application):
    """Setting up login subsystem in application"""

    settings: LoginSettings = app[APP_SETTINGS_KEY].WEBSERVER_LOGIN
    assert settings  # nosec

    # routes
    specs = app[APP_OPENAPI_SPECS_KEY]
    routes = create_routes(specs)
    app.router.add_routes(routes)

    # signals
    app.cleanup_ctx.append(_setup_config_and_pgpool)
    return True
