import logging
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager, State
from models_library.products import ProductName

from ..core.settings import ApplicationSettings, NotificationsSMTPSettings
from ..repositories.product import ProductRepository

_logger = logging.getLogger(__name__)

_OK_ICON = "✅"
_WARNING_ICON = "⚠️"


def _build_status_table(
    product_names: list[ProductName],
    configured_products: set[ProductName],
) -> str:
    name_header = "Product"
    status_header = "SMTP Configured"
    name_width = max([len(name_header), *(len(name) for name in product_names)])

    lines: list[str] = [
        f"{name_header.ljust(name_width)}  {status_header}",
        f"{'-' * name_width}  {'-' * len(status_header)}",
    ]
    for name in product_names:
        is_configured = name in configured_products
        icon = _OK_ICON if is_configured else _WARNING_ICON
        status = f"{icon} {'yes' if is_configured else 'MISSING'}"
        lines.append(f"{name.ljust(name_width)}  {status}")
    return "\n".join(lines)


async def check_smtp_configuration(
    product_repository: ProductRepository,
    smtp_settings: NotificationsSMTPSettings | None,
) -> None:
    """Checks on startup that every product has SMTP settings configured.

    Logs a status table per product and a warning for each product missing
    its SMTP configuration.
    """
    product_names = await product_repository.list_product_names()

    configured_products: set[ProductName] = set(smtp_settings.products) if smtp_settings is not None else set()

    table = _build_status_table(product_names, configured_products)
    _logger.info("SMTP configuration status per product:\n%s", table)

    missing_products = [name for name in product_names if name not in configured_products]
    for product_name in missing_products:
        _logger.warning(
            "SMTP settings are missing for product '%s'. "
            "Emails for this product will fail until it is configured in NOTIFICATIONS_SMTP_SETTINGS.",
            product_name,
        )


async def _smtp_config_check_lifespan(app: FastAPI) -> AsyncIterator[State]:
    settings: ApplicationSettings = app.state.settings
    product_repository = ProductRepository(engine=app.state.engine)

    await check_smtp_configuration(
        product_repository,
        settings.NOTIFICATIONS_SMTP_SETTINGS,
    )

    yield {}


def configure_smtp_config_check(app_lifespan: LifespanManager[FastAPI]) -> None:
    app_lifespan.add(_smtp_config_check_lifespan)
