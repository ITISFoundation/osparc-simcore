""" Common functions to access products table

"""

from typing import Optional, Protocol

import sqlalchemy as sa
from models_library.users import GroupID

from .models.groups import GroupType, groups
from .models.products import products


class _DBConnection(Protocol):
    # Prototype to account for aiopg and asyncio connection classes, i.e.
    #   from aiopg.sa.connection import SAConnection
    #   from sqlalchemy.ext.asyncio import AsyncConnection
    async def scalar(self, *args, **kwargs):
        ...


class _AiopgConnection(Protocol):
    # Prototype to account for aiopg-only (this protocol avoids import <-> installation)
    async def scalar(self, *args, **kwargs):
        ...

    async def execute(self, *args, **kwargs):
        ...

    async def begin(self):
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


async def get_product_group_id(
    connection: _DBConnection, product_name: str
) -> Optional[GroupID]:
    group_id = await connection.scalar(
        sa.select([products.c.group_id]).where(products.c.name == product_name)
    )
    return None if group_id is None else GroupID(group_id)


async def get_or_create_product_group(
    connection: _AiopgConnection, product_name: str
) -> GroupID:
    """
    Returns group_id of a product. Creates it if undefined
    """
    group_id = await get_product_group_id(connection, product_name=product_name)
    if group_id is not None:
        return group_id

    async with connection.begin():
        group_id = await connection.scalar(
            groups.insert()
            .values(
                name=product_name,
                description=f"{product_name} product group",
                type=GroupType.STANDARD,
            )
            .returning(groups.c.gid)
        )
        assert group_id  # nosec

        await connection.execute(
            products.update()
            .where(products.c.name == product_name)
            .values(group_id=group_id)
        )
        return GroupID(group_id)
