import logging
from collections.abc import AsyncIterator
from decimal import Decimal
from typing import NamedTuple

import sqlalchemy as sa
from aiopg.sa.connection import SAConnection
from aiopg.sa.result import ResultProxy, RowProxy
from models_library.basic_types import NonNegativeDecimal
from models_library.products import ProductName, ProductStripeInfoGet
from pydantic import parse_obj_as
from simcore_postgres_database.constants import QUANTIZE_EXP_ARG
from simcore_postgres_database.models.products import jinja2_templates
from simcore_postgres_database.utils_products_prices import (
    get_product_latest_credit_price_or_none,
    get_product_latest_stripe_info,
)

from ..db.base_repository import BaseRepository
from ..db.models import products
from ._model import Product

_logger = logging.getLogger(__name__)


#
# REPOSITORY
#

# NOTE: This also asserts that all model fields are in sync with sqlalchemy columns
_PRODUCTS_COLUMNS = [
    products.c.name,
    products.c.display_name,
    products.c.short_name,
    products.c.host_regex,
    products.c.support_email,
    products.c.twilio_messaging_sid,
    products.c.vendor,
    products.c.issues,
    products.c.manuals,
    products.c.support,
    products.c.login_settings,
    products.c.registration_email_template,
    products.c.max_open_studies_per_user,
    products.c.group_id,
]


class PaymentFieldsTuple(NamedTuple):
    enabled: bool
    credits_per_usd: Decimal | None


async def get_product_payment_fields(
    conn: SAConnection, product_name: ProductName
) -> PaymentFieldsTuple:
    usd_per_credit = await get_product_latest_credit_price_or_none(
        conn, product_name=product_name
    )
    if usd_per_credit is None or usd_per_credit == 0:
        enabled = False
        credits_per_usd = None
    else:
        enabled = True
        credits_per_usd = Decimal(1 / usd_per_credit).quantize(QUANTIZE_EXP_ARG)

    return PaymentFieldsTuple(enabled=enabled, credits_per_usd=credits_per_usd)


async def iter_products(conn: SAConnection) -> AsyncIterator[ResultProxy]:
    """Iterates on products sorted by priority i.e. the first is considered the default"""
    async for row in conn.execute(
        sa.select(*_PRODUCTS_COLUMNS).order_by(products.c.priority)
    ):
        assert row  # nosec
        yield row


class ProductRepository(BaseRepository):
    async def get_product(self, product_name: str) -> Product | None:
        async with self.engine.acquire() as conn:
            result: ResultProxy = await conn.execute(
                sa.select(*_PRODUCTS_COLUMNS).where(products.c.name == product_name)
            )
            row: RowProxy | None = await result.first()
            if row:
                # NOTE: MD Observation: Currently we are not defensive, we assume automatically
                # that the product is not billable when there is no product in the products_prices table
                # or it's price is 0. We should change it and always assume that the product is billable, unless
                # explicitely stated that it is free
                payments = await get_product_payment_fields(conn, product_name=row.name)
                return Product(
                    **dict(row.items()),
                    is_payment_enabled=payments.enabled,
                    credits_per_usd=payments.credits_per_usd,
                )
            return None

    async def get_product_latest_credit_price_or_none(
        self, product_name: str
    ) -> NonNegativeDecimal | None:
        async with self.engine.acquire() as conn:
            # newest price of a product
            usd_per_credit = await get_product_latest_credit_price_or_none(
                conn, product_name=product_name
            )
            return parse_obj_as(NonNegativeDecimal | None, usd_per_credit)

    async def get_product_stripe_info(self, product_name: str) -> ProductStripeInfoGet:
        async with self.engine.acquire() as conn:
            row = await get_product_latest_stripe_info(conn, product_name=product_name)
            return ProductStripeInfoGet(
                stripe_price_id=row[0], stripe_tax_rate_id=row[1]
            )

    async def get_template_content(
        self,
        template_name: str,
    ) -> str | None:
        async with self.engine.acquire() as conn:
            template_content: str | None = await conn.scalar(
                sa.select(jinja2_templates.c.content).where(
                    jinja2_templates.c.name == template_name
                )
            )
            return template_content

    async def get_product_template_content(
        self,
        product_name: str,
        product_template: sa.Column = products.c.registration_email_template,
    ) -> str | None:
        async with self.engine.acquire() as conn:
            oj = sa.join(
                products,
                jinja2_templates,
                product_template == jinja2_templates.c.name,
                isouter=True,
            )
            content = await conn.scalar(
                sa.select(jinja2_templates.c.content)
                .select_from(oj)
                .where(products.c.name == product_name)
            )
            return f"{content}" if content else None
