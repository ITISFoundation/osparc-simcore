import asyncio
import logging
from typing import Final

import asyncpg
from aiohttp import web
from pydantic import ValidationError
from settings_library.email import SMTPSettings
from settings_library.postgres import PostgresSettings

from .._meta import APP_NAME
from ..application_keys import APP_SETTINGS_KEY
from ..application_setup import (
    ModuleCategory,
    app_setup_func,
    ensure_single_setup,
)
from ..constants import (
    APP_PUBLIC_CONFIG_PER_PRODUCT,
    INDEX_RESOURCE_NAME,
)
from ..db.plugin import setup_db
from ..db.settings import get_plugin_settings as get_db_plugin_settings
from ..email.plugin import setup_email
from ..email.settings import get_plugin_settings as get_email_plugin_settings
from ..invitations.plugin import setup_invitations
from ..login_accounts.plugin import setup_login_account
from ..login_auth.plugin import setup_login_auth
from ..products import products_service
from ..products.models import ProductName
from ..products.plugin import setup_products
from ..redis import setup_redis
from ..rest.plugin import setup_rest
from ._controller.rest import (
    auth,
    change,
    confirmation,
    registration,
    twofa,
)
from ._login_repository_legacy import APP_LOGIN_STORAGE_KEY, AsyncpgStorage
from .constants import APP_LOGIN_SETTINGS_PER_PRODUCT_KEY
from .settings import (
    APP_LOGIN_OPTIONS_KEY,
    LoginOptions,
    LoginSettings,
    LoginSettingsForProduct,
)

log = logging.getLogger(__name__)

APP_LOGIN_CLIENT_KEY: Final = web.AppKey("APP_LOGIN_CLIENT_KEY", object)

MAX_TIME_TO_CLOSE_POOL_SECS = 5


async def _setup_login_storage_ctx(app: web.Application):
    assert APP_LOGIN_STORAGE_KEY not in app  # nosec
    settings: PostgresSettings = get_db_plugin_settings(app)

    async with asyncpg.create_pool(
        dsn=settings.dsn_with_query(f"{APP_NAME}-login", suffix="asyncpg"),
        min_size=settings.POSTGRES_MINSIZE,
        max_size=settings.POSTGRES_MAXSIZE,
        loop=asyncio.get_event_loop(),
    ) as pool:
        app[APP_LOGIN_STORAGE_KEY] = AsyncpgStorage(pool)

        yield  # ----------------


@ensure_single_setup(f"{__name__}.storage", logger=log)
def setup_login_storage(app: web.Application):
    if _setup_login_storage_ctx not in app.cleanup_ctx:
        app.cleanup_ctx.append(_setup_login_storage_ctx)


@ensure_single_setup(f"{__name__}.login_options", logger=log)
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
        for product in products_service.list_products(app):
            try:
                login_settings_per_product[product.name] = (
                    LoginSettingsForProduct.create_from_composition(
                        app_login_settings=app_login_settings,
                        product_login_settings=product.login_settings,
                    )
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


@app_setup_func(
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

    app.router.add_routes(auth.routes)
    setup_login_auth(app)
    setup_login_account(app)

    app.router.add_routes(confirmation.routes)
    app.router.add_routes(registration.routes)
    app.router.add_routes(change.routes)
    app.router.add_routes(twofa.routes)

    _setup_login_options(app)
    setup_login_storage(app)

    app.on_startup.append(_resolve_login_settings_per_product)

    return True
