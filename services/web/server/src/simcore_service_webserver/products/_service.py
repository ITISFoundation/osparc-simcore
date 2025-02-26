from decimal import Decimal
from typing import Any, cast

from aiohttp import web
from models_library.products import CreditResultGet, ProductName, ProductStripeInfoGet
from simcore_postgres_database.utils_products_prices import ProductPriceInfo

from ..constants import APP_PRODUCTS_KEY
from ._repository import ProductRepository
from .errors import (
    BelowMinimumPaymentError,
    ProductNotFoundError,
    ProductPriceNotDefinedError,
    ProductTemplateNotFoundError,
)
from .models import Product


def get_product(app: web.Application, product_name: ProductName) -> Product:
    product: Product = app[APP_PRODUCTS_KEY][product_name]
    return product


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
    return cast(  # mypy: not sure why
        ProductPriceInfo | None,
        await repo.get_product_latest_price_info_or_none(product_name),
    )


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
) -> CreditResultGet:
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
            reason=f"Product {product_name} usd_per_credit is either not defined or zero"
        )

    if dollar_amount < price_info.min_payment_amount_usd:
        raise BelowMinimumPaymentError(
            amount_usd=dollar_amount,
            min_payment_amount_usd=price_info.min_payment_amount_usd,
        )

    credit_amount = dollar_amount / price_info.usd_per_credit
    return CreditResultGet(product_name=product_name, credit_amount=credit_amount)


async def get_product_stripe_info(
    app: web.Application, *, product_name: ProductName
) -> ProductStripeInfoGet:
    repo = ProductRepository.create_from_app(app)
    product_stripe_info = await repo.get_product_stripe_info(product_name)
    if (
        not product_stripe_info
        or "missing!!" in product_stripe_info.stripe_price_id
        or "missing!!" in product_stripe_info.stripe_tax_rate_id
    ):
        msg = f"Missing product stripe for product {product_name}"
        raise ValueError(msg)
    return cast(ProductStripeInfoGet, product_stripe_info)  # mypy: not sure why


async def get_template_content(app: web.Application, *, template_name: str):
    repo = ProductRepository.create_from_app(app)
    content = await repo.get_template_content(template_name)
    if not content:
        raise ProductTemplateNotFoundError(template_name=template_name)
    return content
