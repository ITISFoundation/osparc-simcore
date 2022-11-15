""" Common functions to access products table

"""

from typing import Protocol

import sqlalchemy as sa

from .models.products import products


class _DBConnection(Protocol):
    # Prototype to account for aiopg and asyncio connection classes, i.e.
    #   from aiopg.sa.connection import SAConnection
    #   from sqlalchemy.ext.asyncio import AsyncConnection
    async def scalar(self, *args, **kwargs):
        ...


async def get_default_product_name(conn: _DBConnection) -> str:
    """The first row in the table is considered as the default product

    :: raises ValueError if undefined
    """
    product_name = await conn.scalar(
        sa.select([products.c.name]).order_by(products.c.priority)
    )
    if not product_name:
        raise ValueError("No product defined in database")

    assert isinstance(product_name, str)  # nosec
    return product_name
