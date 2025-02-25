from decimal import Decimal
from typing import NamedTuple, TypeAlias

import sqlalchemy as sa
from aiopg.sa.connection import SAConnection

from .constants import QUANTIZE_EXP_ARG
from .models.products_prices import products_prices

StripePriceID: TypeAlias = str
StripeTaxRateID: TypeAlias = str


class ProductPriceInfo(NamedTuple):
    usd_per_credit: Decimal
    min_payment_amount_usd: Decimal


async def get_product_latest_price_info_or_none(
    conn: SAConnection, product_name: str
) -> ProductPriceInfo | None:
    """None menans the product is not billable"""
    # newest price of a product
    result = await conn.execute(
        sa.select(
            products_prices.c.usd_per_credit,
            products_prices.c.min_payment_amount_usd,
        )
        .where(products_prices.c.product_name == product_name)
        .order_by(sa.desc(products_prices.c.valid_from))
        .limit(1)
    )
    row = await result.first()

    if row and row.usd_per_credit is not None:
        assert row.min_payment_amount_usd is not None  # nosec
        return ProductPriceInfo(
            usd_per_credit=Decimal(row.usd_per_credit).quantize(QUANTIZE_EXP_ARG),
            min_payment_amount_usd=Decimal(row.min_payment_amount_usd).quantize(
                QUANTIZE_EXP_ARG
            ),
        )
    return None


async def get_product_latest_stripe_info(
    conn: SAConnection, product_name: str
) -> tuple[StripePriceID, StripeTaxRateID]:
    # Stripe info of a product for latest price
    row = await (
        await conn.execute(
            sa.select(
                products_prices.c.stripe_price_id,
                products_prices.c.stripe_tax_rate_id,
            )
            .where(products_prices.c.product_name == product_name)
            .order_by(sa.desc(products_prices.c.valid_from))
            .limit(1)
        )
    ).fetchone()
    if row is None:
        msg = f"No product Stripe info defined in database [{product_name=}]"
        raise ValueError(msg)
    return (row.stripe_price_id, row.stripe_tax_rate_id)


async def is_payment_enabled(conn: SAConnection, product_name: str) -> bool:
    p = await get_product_latest_price_info_or_none(conn, product_name=product_name)
    return bool(p)  # zero or None is disabled
