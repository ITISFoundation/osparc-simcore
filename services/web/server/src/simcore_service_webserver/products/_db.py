import logging
from collections.abc import AsyncIterator
from decimal import Decimal

import sqlalchemy as sa
from aiopg.sa.connection import SAConnection
from aiopg.sa.result import ResultProxy, RowProxy
from simcore_postgres_database.models.products import jinja2_templates
from simcore_postgres_database.utils_products_prices import (
    get_product_latest_price_or_none,
)

from ..db.base_repository import BaseRepository
from ..db.models import products
from ._model import Product

_logger = logging.getLogger(__name__)


#
# REPOSITORY
#

# NOTE: This also asserts that all model fields are in sync with sqlalchemy columns
_COLUMNS_IN_MODEL = [products.columns[f] for f in Product.__fields__]


async def iter_products(conn: SAConnection) -> AsyncIterator[ResultProxy]:
    """Iterates on products sorted by priority i.e. the first is considered the default"""
    async for row in conn.execute(
        sa.select(*_COLUMNS_IN_MODEL).order_by(products.c.priority)
    ):
        assert row  # nosec
        yield row


class ProductRepository(BaseRepository):
    async def get_product(self, product_name: str) -> Product | None:
        async with self.engine.acquire() as conn:
            result: ResultProxy = await conn.execute(
                sa.select(_COLUMNS_IN_MODEL).where(products.c.name == product_name)
            )
            row: RowProxy | None = await result.first()
            return Product.from_orm(row) if row else None

    async def get_product_latest_price_or_none(
        self, product_name: str
    ) -> Decimal | None:
        async with self.engine.acquire() as conn:
            # newest price of a product
            usd_per_credit: Decimal | None = await get_product_latest_price_or_none(
                conn, product_name=product_name
            )
            return usd_per_credit

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
