import asyncio
import logging

import asyncpg
from aiohttp import web
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup

from .._constants import APP_OPENAPI_SPECS_KEY, INDEX_RESOURCE_NAME
from ..db import setup_db
from ..db_settings import PostgresSettings
from ..db_settings import get_plugin_settings as get_db_plugin_settings
from ..email import setup_email
from ..email_settings import SMTPSettings
from ..email_settings import get_plugin_settings as get_email_plugin_settings
from ..products import setup_products
from ..redis import setup_redis
from ..rest import setup_rest
from .routes import create_routes
from .settings import APP_LOGIN_OPTIONS_KEY, LoginOptions
from .storage import APP_LOGIN_STORAGE_KEY, AsyncpgStorage

log = logging.getLogger(__name__)


MAX_TIME_TO_CLOSE_POOL_SECS = 5


async def _setup_login_storage_ctx(app: web.Application):
    assert APP_LOGIN_STORAGE_KEY not in app  # nosec
    settings: PostgresSettings = get_db_plugin_settings(app)

    pool: asyncpg.pool.Pool = await asyncpg.create_pool(
        dsn=settings.dsn_with_query,
        min_size=settings.POSTGRES_MINSIZE,
        max_size=settings.POSTGRES_MAXSIZE,
        loop=asyncio.get_event_loop(),
    )
    app[APP_LOGIN_STORAGE_KEY] = storage = AsyncpgStorage(pool)

    yield  # ----------------

    if storage.pool is not pool:
        log.error("Somebody has changed the db pool")

    try:
        await asyncio.wait_for(pool.close(), timeout=MAX_TIME_TO_CLOSE_POOL_SECS)
    except asyncio.TimeoutError:
        log.exception("Failed to close login storage loop")


def setup_login_storage(app: web.Application):
    if _setup_login_storage_ctx not in app.cleanup_ctx:
        app.cleanup_ctx.append(_setup_login_storage_ctx)


def _setup_login_options(app: web.Application):
    settings: SMTPSettings = get_email_plugin_settings(app)

    cfg = settings.dict()
    if INDEX_RESOURCE_NAME in app.router:
        cfg["LOGIN_REDIRECT"] = f"{app.router[INDEX_RESOURCE_NAME].url_for()}"

    app[APP_LOGIN_OPTIONS_KEY] = LoginOptions(**cfg)


@app_module_setup(
    "simcore_service_webserver.login",
    ModuleCategory.ADDON,
    settings_name="WEBSERVER_LOGIN",
    logger=log,
)
def setup_login(app: web.Application):
    """Setting up login subsystem in application"""

    setup_db(app)
    setup_redis(app)
    setup_products(app)
    setup_rest(app)
    setup_email(app)

    # routes
    specs = app[APP_OPENAPI_SPECS_KEY]
    routes = create_routes(specs)
    app.router.add_routes(routes)

    _setup_login_options(app)
    setup_login_storage(app)
    return True
