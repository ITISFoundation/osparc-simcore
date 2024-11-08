import asyncio
import logging

import asyncpg
from aiohttp import web
from pydantic import ValidationError
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup
from settings_library.email import SMTPSettings
from settings_library.postgres import PostgresSettings

from .._constants import (
    APP_PUBLIC_CONFIG_PER_PRODUCT,
    APP_SETTINGS_KEY,
    INDEX_RESOURCE_NAME,
)
from ..db.plugin import setup_db
from ..db.settings import get_plugin_settings as get_db_plugin_settings
from ..email.plugin import setup_email
from ..email.settings import get_plugin_settings as get_email_plugin_settings
from ..invitations.plugin import setup_invitations
from ..products.api import ProductName, list_products
from ..products.plugin import setup_products
from ..redis import setup_redis
from ..rest.plugin import setup_rest
from . import (
    _2fa_handlers,
    _auth_handlers,
    _registration_handlers,
    handlers_change,
    handlers_confirmation,
    handlers_registration,
)
from ._constants import APP_LOGIN_SETTINGS_PER_PRODUCT_KEY
from .settings import (
    APP_LOGIN_OPTIONS_KEY,
    LoginOptions,
    LoginSettings,
    LoginSettingsForProduct,
)
from .storage import APP_LOGIN_STORAGE_KEY, AsyncpgStorage

log = logging.getLogger(__name__)


MAX_TIME_TO_CLOSE_POOL_SECS = 5


async def _setup_login_storage_ctx(app: web.Application):
    assert APP_LOGIN_STORAGE_KEY not in app  # nosec
    settings: PostgresSettings = get_db_plugin_settings(app)

    async with asyncpg.create_pool(
        dsn=settings.dsn_with_query,
        min_size=settings.POSTGRES_MINSIZE,
        max_size=settings.POSTGRES_MAXSIZE,
        loop=asyncio.get_event_loop(),
    ) as pool:
        app[APP_LOGIN_STORAGE_KEY] = AsyncpgStorage(pool)

        yield  # ----------------


def setup_login_storage(app: web.Application):
    if _setup_login_storage_ctx not in app.cleanup_ctx:
        app.cleanup_ctx.append(_setup_login_storage_ctx)


def _setup_login_options(app: web.Application):
    settings: SMTPSettings = get_email_plugin_settings(app)

    cfg = settings.model_dump()
    if INDEX_RESOURCE_NAME in app.router:
        cfg["LOGIN_REDIRECT"] = f"{app.router[INDEX_RESOURCE_NAME].url_for()}"

    app[APP_LOGIN_OPTIONS_KEY] = LoginOptions(**cfg)


async def _resolve_login_settings_per_product(app: web.Application):
    """Resolves login settings by composing app and product configurations
    for the login plugin. Note that product settings override app settings.
    """
    # app plugin settings
    app_login_settings: LoginSettings | None
    login_settings_per_product: dict[ProductName, LoginSettingsForProduct] = {}

    if app_login_settings := app[APP_SETTINGS_KEY].WEBSERVER_LOGIN:
        assert app_login_settings, "setup_settings not called?"  # nosec
        assert isinstance(app_login_settings, LoginSettings)  # nosec

        # compose app and product settings

        errors = {}
        for product in list_products(app):
            try:
                login_settings_per_product[
                    product.name
                ] = LoginSettingsForProduct.create_from_composition(
                    app_login_settings=app_login_settings,
                    product_login_settings=product.login_settings,
                )
            except ValidationError as err:  # noqa: PERF203
                errors[product.name] = err

        if errors:
            msg = "\n".join([f"{n}: {e}" for n, e in errors.items()])
            error_msg = f"Invalid product.login_settings:\n{msg}"
            raise ValueError(error_msg)

    # store in app
    app[APP_LOGIN_SETTINGS_PER_PRODUCT_KEY] = login_settings_per_product

    # product-based public config: Overrides  ApplicationSettings.public_dict
    public_data_per_product = {}
    for product_name, settings in login_settings_per_product.items():
        public_data_per_product[product_name] = {
            "invitation_required": settings.LOGIN_REGISTRATION_INVITATION_REQUIRED
        }

    app.setdefault(APP_PUBLIC_CONFIG_PER_PRODUCT, public_data_per_product)


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
    setup_invitations(app)

    # routes

    app.router.add_routes(_auth_handlers.routes)
    app.router.add_routes(handlers_confirmation.routes)
    app.router.add_routes(handlers_registration.routes)
    app.router.add_routes(_registration_handlers.routes)
    app.router.add_routes(handlers_change.routes)
    app.router.add_routes(_2fa_handlers.routes)

    _setup_login_options(app)
    setup_login_storage(app)

    app.on_startup.append(_resolve_login_settings_per_product)

    return True
