import logging
from collections.abc import AsyncIterator
from decimal import Decimal
from typing import Any, NamedTuple

import sqlalchemy as sa
from aiohttp import web
from aiopg.sa.connection import SAConnection
from aiopg.sa.result import ResultProxy
from models_library.products import ProductName, ProductStripeInfoGet
from simcore_postgres_database.constants import QUANTIZE_EXP_ARG
from simcore_postgres_database.models.jinja2_templates import jinja2_templates
from simcore_postgres_database.utils_products import (
    get_or_create_product_group,
)
from simcore_postgres_database.utils_products_prices import (
    ProductPriceInfo,
    get_product_latest_price_info_or_none,
    get_product_latest_stripe_info,
)
from simcore_postgres_database.utils_repos import pass_or_acquire_connection
from simcore_service_webserver.constants import FRONTEND_APPS_AVAILABLE
from sqlalchemy.ext.asyncio import AsyncConnection

from ..constants import FRONTEND_APPS_AVAILABLE
from ..db.base_repository import BaseRepositoryV2
from ..db.models import products
from ..db.plugin import get_database_engine
from ._repository import get_product_payment_fields, iter_products
from .models import Product

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
    products.c.product_owners_email,
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
    min_payment_amount_usd: Decimal | None


async def get_product_payment_fields(
    conn: SAConnection, product_name: ProductName
) -> PaymentFieldsTuple:
    price_info = await get_product_latest_price_info_or_none(
        conn, product_name=product_name
    )
    if price_info is None or price_info.usd_per_credit == 0:
        return PaymentFieldsTuple(
            enabled=False,
            credits_per_usd=None,
            min_payment_amount_usd=None,
        )

    assert price_info.usd_per_credit > 0
    assert price_info.min_payment_amount_usd > 0

    return PaymentFieldsTuple(
        enabled=True,
        credits_per_usd=Decimal(1 / price_info.usd_per_credit).quantize(
            QUANTIZE_EXP_ARG
        ),
        min_payment_amount_usd=price_info.min_payment_amount_usd,
    )


async def auto_create_products_groups(app: web.Application) -> None:
    """Ensures all products have associated group ids

    Avoids having undefined groups in products with new products.group_id column

    NOTE: could not add this in 'setup_groups' (groups plugin)
    since it has to be executed BEFORE 'load_products_on_startup'
    """
    engine = get_database_engine(app)

    async with engine.acquire() as connection:
        async for row in iter_products(connection):
            product_name = row.name  # type: ignore[attr-defined] # sqlalchemy
            product_group_id = await get_or_create_product_group(
                connection, product_name
            )
            _logger.debug(
                "Product with %s has an associated group with %s",
                f"{product_name=}",
                f"{product_group_id=}",
            )


async def iter_products(conn: AsyncConnection) -> AsyncIterator[ResultProxy]:
    """Iterates on products sorted by priority i.e. the first is considered the default"""
    async for row in conn.stream(
        sa.select(*_PRODUCTS_COLUMNS).order_by(products.c.priority)
    ):
        assert row  # nosec
        yield row


class ProductRepository(BaseRepositoryV2):

    async def list_products(
        self,
        connection: AsyncConnection | None = None,
    ) -> list[Product]:
        """
        Raises:
            ValidationError:if products are not setup correctly in the database
        """
        app_products: list[Product] = []

        query = sa.select(*_PRODUCTS_COLUMNS).order_by(products.c.priority)

        async with pass_or_acquire_connection(self.engine, connection) as conn:
            rows = await conn.stream(query)
            async for row in rows:
                name = row.name

                payments = await get_product_payment_fields(conn, product_name=name)

                app_products.append(
                    Product(
                        **dict(row.items()),
                        is_payment_enabled=payments.enabled,
                        credits_per_usd=payments.credits_per_usd,
                    )
                )

                assert name in FRONTEND_APPS_AVAILABLE  # nosec

        return app_products

    async def list_products_names(
        self,
        connection: AsyncConnection | None = None,
    ) -> list[ProductName]:
        query = sa.select(products.c.name).order_by(products.c.priority)

        async with pass_or_acquire_connection(self.engine, connection) as conn:
            rows = await conn.stream(query)
            return [ProductName(row.name) async for row in rows]

    async def get_product(
        self, product_name: str, connection: AsyncConnection | None = None
    ) -> Product | None:
        query = sa.select(*_PRODUCTS_COLUMNS).where(products.c.name == product_name)

        async with pass_or_acquire_connection(self.engine, connection) as conn:

            result = await conn.execute(query)
            row = result.one_or_none()
            if row:
                payments = await get_product_payment_fields(conn, product_name=row.name)
                return Product(
                    **row._asdict(),
                    is_payment_enabled=payments.enabled,
                    credits_per_usd=payments.credits_per_usd,
                )
            return None

    async def get_default_product_name(
        self, connection: AsyncConnection | None = None
    ) -> ProductName:
        raise NotImplementedError

    async def get_product_latest_price_info_or_none(
        self, product_name: str, connection: AsyncConnection | None = None
    ) -> ProductPriceInfo | None:
        async with pass_or_acquire_connection(self.engine, connection) as conn:
            return await get_product_latest_price_info_or_none(
                conn, product_name=product_name
            )

    async def get_product_stripe_info(
        self, product_name: str, connection: AsyncConnection | None = None
    ) -> ProductStripeInfoGet:
        async with pass_or_acquire_connection(self.engine, connection) as conn:
            row = await get_product_latest_stripe_info(conn, product_name=product_name)
            return ProductStripeInfoGet(
                stripe_price_id=row[0], stripe_tax_rate_id=row[1]
            )

    async def get_template_content(
        self, template_name: str, connection: AsyncConnection | None = None
    ) -> str | None:
        query = sa.select(jinja2_templates.c.content).where(
            jinja2_templates.c.name == template_name
        )

        async with pass_or_acquire_connection(self.engine, connection) as conn:
            template_content: str | None = await conn.scalar(query)
            return template_content

    async def get_product_template_content(
        self,
        product_name: str,
        product_template: sa.Column = products.c.registration_email_template,
        connection: AsyncConnection | None = None,
    ) -> str | None:
        query = (
            sa.select(jinja2_templates.c.content)
            .select_from(
                sa.join(
                    products,
                    jinja2_templates,
                    product_template == jinja2_templates.c.name,
                    isouter=True,
                )
            )
            .where(products.c.name == product_name)
        )

        async with pass_or_acquire_connection(self.engine, connection) as conn:
            template_content: str | None = await conn.scalar(query)
            return template_content

    async def get_product_ui(
        self, product_name: ProductName, connection: AsyncConnection | None = None
    ) -> dict[str, Any] | None:
        query = sa.select(products.c.ui).where(products.c.name == product_name)

        async with pass_or_acquire_connection(self.engine, connection) as conn:
            result = await conn.execute(query)
            row = result.one_or_none()
            return dict(**row.ui) if row else None
