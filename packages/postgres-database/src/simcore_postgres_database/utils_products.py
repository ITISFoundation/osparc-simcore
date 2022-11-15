""" Common functions to access products table

"""

import sqlalchemy as sa
from aiopg.sa.connection import SAConnection

from .models.products import products


async def get_default_product_name(conn: SAConnection) -> str:
    """The first row in the table is considered as the default product

    :: raises ValueError if undefined
    """
    product_name = await conn.scalar(sa.select([products.c.name]))
    if not product_name:
        raise ValueError("No product defined in database")

    assert isinstance(product_name, str)  # nosec
    return product_name
