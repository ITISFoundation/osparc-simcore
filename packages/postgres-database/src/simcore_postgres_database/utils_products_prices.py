from decimal import Decimal

import sqlalchemy as sa
from aiopg.sa.connection import SAConnection

from .constants import QUANTIZE_EXP_ARG
from .models.products_prices import products_prices


async def get_product_latest_credit_price_or_none(
    conn: SAConnection, product_name: str
) -> Decimal | None:
    # newest price of a product
    usd_per_credit = await conn.scalar(
        sa.select(products_prices.c.usd_per_credit)
        .where(products_prices.c.product_name == product_name)
        .order_by(sa.desc(products_prices.c.valid_from))
        .limit(1)
    )
    if usd_per_credit is not None:
        return Decimal(usd_per_credit).quantize(QUANTIZE_EXP_ARG)
    return None


async def is_payment_enabled(conn: SAConnection, product_name: str) -> bool:
    p = await get_product_latest_credit_price_or_none(conn, product_name=product_name)
    return bool(p)  # zero or None is disabled
