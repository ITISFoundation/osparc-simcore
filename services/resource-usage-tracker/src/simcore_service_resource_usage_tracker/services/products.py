from models_library.products import ProductName
from simcore_postgres_database.utils_products import ProductEmailInfo
from simcore_postgres_database.utils_products import (
    get_product_email_info as _get_product_email_info,
)
from simcore_postgres_database.utils_repos import transaction_context
from sqlalchemy.ext.asyncio import AsyncEngine


async def get_product_email_info(
    db_engine: AsyncEngine,
    *,
    product_name: ProductName,
) -> ProductEmailInfo:
    async with transaction_context(db_engine) as conn:
        return await _get_product_email_info(conn, product_name)
