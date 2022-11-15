import logging
from typing import AsyncIterator, Optional

import sqlalchemy as sa
from aiopg.sa.engine import Engine
from aiopg.sa.result import ResultProxy, RowProxy
from simcore_postgres_database.models.products import jinja2_templates

from .db_base_repository import BaseRepository
from .db_models import products
from .products_model import Product

log = logging.getLogger(__name__)


#
# REPOSITORY
#

# NOTE: This also asserts that all model fields are in sync with sqlalchemy columns
_COLUMNS_IN_MODEL = [products.columns[f] for f in Product.__fields__]


async def iter_products(engine: Engine) -> AsyncIterator[ResultProxy]:
    """Iterates on products sorted by priority i.e. the first is considered the default"""
    async with engine.acquire() as conn:
        async for row in conn.execute(
            sa.select(_COLUMNS_IN_MODEL).order_by(products.c.priority)
        ):
            assert row  # nosec
            yield row


class ProductRepository(BaseRepository):
    async def get_product(self, product_name: str) -> Optional[Product]:
        async with self.engine.acquire() as conn:
            result: ResultProxy = await conn.execute(
                sa.select(_COLUMNS_IN_MODEL).where(products.c.name == product_name)
            )
            row: Optional[RowProxy] = await result.first()
            return Product.from_orm(row) if row else None

    async def get_template_content(
        self,
        template_name: str,
    ) -> Optional[str]:
        async with self.engine.acquire() as conn:
            return await conn.scalar(
                sa.select([jinja2_templates.c.content]).where(
                    jinja2_templates.c.name == template_name
                )
            )

    async def get_product_template_content(
        self,
        product_name: str,
        product_template: sa.Column = products.c.registration_email_template,
    ) -> Optional[str]:
        async with self.engine.acquire() as conn:
            oj = sa.join(
                products,
                jinja2_templates,
                product_template == jinja2_templates.c.name,
                isouter=True,
            )
            content = await conn.scalar(
                sa.select([jinja2_templates.c.content])
                .select_from(oj)
                .where(products.c.name == product_name)
            )
            return f"{content}" if content else None
