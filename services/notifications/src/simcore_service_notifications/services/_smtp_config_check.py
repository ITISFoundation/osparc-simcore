import logging
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager, State
from models_library.notifications.rpc import SenderIdentity
from models_library.products import ProductName

from ..core.settings import ApplicationSettings, NotificationsSMTPSettings
from ..repositories.product import ProductRepository

_logger = logging.getLogger(__name__)

_OK_ICON = "✅"
_WARNING_ICON = "⚠️"
# Both icons render as 2 terminal columns regardless of their Python str length.
_ICON_DISPLAY_WIDTH = 2
_MISSING_VALUE = "—"


def _make_cell(text: str, *, icon: str | None = None) -> tuple[str, int]:
    """Returns (rendered_text, display_width) for a single table cell.

    A leading icon always renders as ``_ICON_DISPLAY_WIDTH`` terminal columns,
    so the display width is computed independently of ``len()``.
    """
    if icon is None:
        return text, len(text)
    return f"{icon} {text}", _ICON_DISPLAY_WIDTH + 1 + len(text)


def _build_status_table(
    product_names: list[ProductName],
    smtp_settings: NotificationsSMTPSettings | None,
) -> str:
    identities = list(SenderIdentity)

    # Header cells have no icon
    header_cells = [
        _make_cell("Product"),
        _make_cell("SMTP Configured"),
        *(_make_cell(f"{identity}") for identity in identities),
    ]

    rows: list[list[tuple[str, int]]] = []
    for name in product_names:
        product_settings = smtp_settings.products.get(name) if smtp_settings is not None else None
        is_configured = product_settings is not None

        status_cell = _make_cell(
            "yes" if is_configured else "MISSING",
            icon=_OK_ICON if is_configured else _WARNING_ICON,
        )

        identity_cells: list[tuple[str, int]] = []
        for identity in identities:
            local_part = product_settings.local_parts.get(identity) if product_settings is not None else None
            if local_part is not None:
                identity_cells.append(_make_cell(f"{local_part}@{product_settings.domain}", icon=_OK_ICON))
            else:
                identity_cells.append(_make_cell(_MISSING_VALUE, icon=_WARNING_ICON))

        rows.append([_make_cell(name), status_cell, *identity_cells])

    # Compute the display width of each column
    num_columns = len(header_cells)
    col_widths = [
        max(header_cells[col][1], *(row[col][1] for row in rows)) if rows else header_cells[col][1]
        for col in range(num_columns)
    ]

    def _format_row(cells: list[tuple[str, int]]) -> str:
        return "  ".join(text + " " * (col_widths[col] - width) for col, (text, width) in enumerate(cells))

    border = "  ".join("-" * width for width in col_widths)
    lines = [border, _format_row(header_cells), border]
    lines.extend(_format_row(row) for row in rows)
    lines.append(border)
    return "\n".join(lines)


async def check_smtp_configuration(
    product_repository: ProductRepository,
    smtp_settings: NotificationsSMTPSettings | None,
) -> None:
    """Checks on startup that every product has SMTP settings configured.

    Prints a status table per product (so it is visible right before the
    started banner, regardless of log level) and logs a warning for each
    product missing its SMTP configuration.
    """
    product_names = await product_repository.list_product_names()

    configured_products: set[ProductName] = set(smtp_settings.products) if smtp_settings is not None else set()

    table = _build_status_table(product_names, smtp_settings)
    # NOTE: uses print (like the startup banners) so the table is always emitted
    # before the started banner, even when logging level is above INFO.
    print(f"SMTP configuration status per product:\n{table}", flush=True)  # noqa: T201

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
