from decimal import Decimal
from typing import Any

from aiohttp import web
from models_library.groups import GroupID
from models_library.products import ProductName
from pydantic import ValidationError
from servicelib.exceptions import InvalidConfig
from simcore_postgres_database.utils_products_prices import ProductPriceInfo

from ..constants import APP_PRODUCTS_KEY
from ._models import CreditResult, ProductStripeInfo
from ._repository import ProductRepository
from .errors import (
    BelowMinimumPaymentError,
    MissingStripeConfigError,
    ProductNotFoundError,
    ProductPriceNotDefinedError,
    ProductTemplateNotFoundError,
)
from .models import Product


async def load_products(app: web.Application) -> list[Product]:
    repo = ProductRepository.create_from_app(app)
    try:
        # NOTE: list_products implemented as fails-fast!
        return await repo.list_products()
    except ValidationError as err:
        msg = f"Invalid product configuration in db:\n {err}"
        raise InvalidConfig(msg) from err


async def get_default_product_name(app: web.Application) -> ProductName:
    repo = ProductRepository.create_from_app(app)
    return await repo.get_default_product_name()


def get_product(app: web.Application, product_name: ProductName) -> Product:
    try:
        product: Product = app[APP_PRODUCTS_KEY][product_name]
        return product
    except KeyError as exc:
        raise ProductNotFoundError(product_name=product_name) from exc


def list_products(app: web.Application) -> list[Product]:
    products: list[Product] = list(app[APP_PRODUCTS_KEY].values())
    return products


async def list_products_names(app: web.Application) -> list[ProductName]:
    repo = ProductRepository.create_from_app(app)
    names: list[ProductName] = await repo.list_products_names()
    return names


async def get_credit_price_info(
    app: web.Application, product_name: ProductName
) -> ProductPriceInfo | None:
    repo = ProductRepository.create_from_app(app)
    return await repo.get_product_latest_price_info_or_none(product_name)


async def get_product_ui(
    repo: ProductRepository, product_name: ProductName
) -> dict[str, Any]:
    ui = await repo.get_product_ui(product_name=product_name)
    if ui is not None:
        return ui

    raise ProductNotFoundError(product_name=product_name)


async def get_credit_amount(
    app: web.Application,
    *,
    dollar_amount: Decimal,
    product_name: ProductName,
) -> CreditResult:
    """For provided dollars and product gets credit amount.

    NOTE: Contrary to other product api functions (e.g. get_current_product) this function
    gets the latest update from the database. Otherwise, products are loaded
    on startup and cached therefore in those cases would require a restart
    of the service for the latest changes to take effect.

    Raises:
        ProductPriceNotDefinedError
        BelowMinimumPaymentError

    """
    repo = ProductRepository.create_from_app(app)
    price_info = await repo.get_product_latest_price_info_or_none(product_name)
    if price_info is None or not price_info.usd_per_credit:
        # '0 or None' should raise
        raise ProductPriceNotDefinedError(
            details=f"Product {product_name} usd_per_credit is either not defined or zero"
        )

    if dollar_amount < price_info.min_payment_amount_usd:
        raise BelowMinimumPaymentError(
            amount_usd=dollar_amount,
            min_payment_amount_usd=price_info.min_payment_amount_usd,
        )

    credit_amount = dollar_amount / price_info.usd_per_credit
    return CreditResult(product_name=product_name, credit_amount=credit_amount)


async def is_product_billable(
    app: web.Application, *, product_name: ProductName
) -> bool:
    repo = ProductRepository.create_from_app(app)
    return await repo.is_product_billable(product_name=product_name)


async def get_product_stripe_info(
    app: web.Application, *, product_name: ProductName
) -> ProductStripeInfo:
    repo = ProductRepository.create_from_app(app)

    product_stripe_info = await repo.get_product_stripe_info_or_none(product_name)
    if (
        product_stripe_info is None
        or "missing!!" in product_stripe_info.stripe_price_id
        or "missing!!" in product_stripe_info.stripe_tax_rate_id
    ):
        exc = MissingStripeConfigError(
            product_name=product_name,
            product_stripe_info=product_stripe_info,
        )
        exc.add_note("Probably stripe side is not configured")
        raise exc
    return product_stripe_info


async def get_template_content(app: web.Application, *, template_name: str):
    repo = ProductRepository.create_from_app(app)
    content = await repo.get_template_content(template_name)
    if not content:
        raise ProductTemplateNotFoundError(template_name=template_name)
    return content


async def auto_create_products_groups(
    app: web.Application,
) -> dict[ProductName, GroupID]:
    repo = ProductRepository.create_from_app(app)
    return await repo.auto_create_products_groups()
