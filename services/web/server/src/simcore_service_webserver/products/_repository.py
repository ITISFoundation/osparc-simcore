import logging
from decimal import Decimal
from typing import Any

import sqlalchemy as sa
from models_library.groups import GroupID
from models_library.products import ProductName
from simcore_postgres_database.constants import QUANTIZE_EXP_ARG
from simcore_postgres_database.models.jinja2_templates import jinja2_templates
from simcore_postgres_database.models.products import products
from simcore_postgres_database.utils_products import (
    get_default_product_name,
    get_or_create_product_group,
)
from simcore_postgres_database.utils_products_prices import (
    ProductPriceInfo,
    get_product_latest_price_info_or_none,
    get_product_latest_stripe_info_or_none,
    is_payment_enabled,
)
from simcore_postgres_database.utils_repos import (
    pass_or_acquire_connection,
    transaction_context,
)
from sqlalchemy.engine import Row
from sqlalchemy.ext.asyncio import AsyncConnection

from ..constants import FRONTEND_APPS_AVAILABLE
from ..db.base_repository import BaseRepository
from ._models import PaymentFields, Product, ProductStripeInfo

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

assert {column.name for column in _PRODUCTS_COLUMNS}.issubset(  # nosec
    set(Product.model_fields)
)


def _to_domain(products_row: Row, payments: PaymentFields) -> Product:
    return Product(
        **products_row._asdict(),
        is_payment_enabled=payments.enabled,
        credits_per_usd=payments.credits_per_usd,
    )


async def _get_product_payment_fields(
    conn: AsyncConnection, product_name: ProductName
) -> PaymentFields:
    price_info = await get_product_latest_price_info_or_none(
        conn, product_name=product_name
    )
    if price_info is None or price_info.usd_per_credit == 0:
        return PaymentFields(
            enabled=False,
            credits_per_usd=None,
            min_payment_amount_usd=None,
        )

    assert price_info.usd_per_credit > 0  # nosec
    assert price_info.min_payment_amount_usd > 0  # nosec

    return PaymentFields(
        enabled=True,
        credits_per_usd=Decimal(1 / price_info.usd_per_credit).quantize(
            QUANTIZE_EXP_ARG
        ),
        min_payment_amount_usd=price_info.min_payment_amount_usd,
    )


class ProductRepository(BaseRepository):

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
                payments = await _get_product_payment_fields(conn, product_name=name)
                app_products.append(_to_domain(row, payments))

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
            if row := result.one_or_none():
                payments = await _get_product_payment_fields(
                    conn, product_name=row.name
                )
                return _to_domain(row, payments)
            return None

    async def get_default_product_name(
        self, connection: AsyncConnection | None = None
    ) -> ProductName:
        async with pass_or_acquire_connection(self.engine, connection) as conn:
            return await get_default_product_name(conn)

    async def get_product_latest_price_info_or_none(
        self, product_name: str, connection: AsyncConnection | None = None
    ) -> ProductPriceInfo | None:
        async with pass_or_acquire_connection(self.engine, connection) as conn:
            return await get_product_latest_price_info_or_none(
                conn, product_name=product_name
            )

    async def get_product_stripe_info_or_none(
        self, product_name: str, connection: AsyncConnection | None = None
    ) -> ProductStripeInfo | None:
        async with pass_or_acquire_connection(self.engine, connection) as conn:
            latest_stripe_info = await get_product_latest_stripe_info_or_none(
                conn, product_name=product_name
            )
            if latest_stripe_info is None:
                return None

            stripe_price_id, stripe_tax_rate_id = latest_stripe_info
            return ProductStripeInfo(
                stripe_price_id=stripe_price_id, stripe_tax_rate_id=stripe_tax_rate_id
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

    async def auto_create_products_groups(
        self,
        connection: AsyncConnection | None = None,
    ) -> dict[ProductName, GroupID]:
        product_groups_map: dict[ProductName, GroupID] = {}

        product_names = await self.list_products_names(connection)
        for product_name in product_names:
            # NOTE: transaction is per product. fail-fast!
            async with transaction_context(self.engine, connection) as conn:
                product_group_id: GroupID = await get_or_create_product_group(
                    conn, product_name
                )
                product_groups_map[product_name] = product_group_id

        return product_groups_map

    async def is_product_billable(
        self, product_name: str, connection: AsyncConnection | None = None
    ) -> bool:
        """This function returns False even if the product price is defined, but is 0"""
        async with pass_or_acquire_connection(self.engine, connection) as conn:
            return await is_payment_enabled(conn, product_name=product_name)
