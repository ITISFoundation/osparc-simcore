"""Common functions to access products table"""

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncConnection

from .models.groups import GroupType, groups
from .models.products import products

# NOTE: outside this module, use instead packages/models-library/src/models_library/users.py
_GroupID = int


async def get_default_product_name(conn: AsyncConnection) -> str:
    """The first row in the table is considered as the default product

    :: raises ValueError if undefined
    """
    product_name = await conn.scalar(
        sa.select(products.c.name).order_by(products.c.priority)
    )
    if not product_name:
        msg = "No product defined in database"
        raise ValueError(msg)

    assert isinstance(product_name, str)  # nosec
    return product_name


async def get_product_group_id(
    connection: AsyncConnection, product_name: str
) -> _GroupID | None:
    group_id = await connection.scalar(
        sa.select(products.c.group_id).where(products.c.name == product_name)
    )
    return None if group_id is None else _GroupID(group_id)


async def execute_get_or_create_product_group(
    conn: AsyncConnection, product_name: str
) -> int:
    #
    # NOTE: Separated so it can be used in asyncpg and aiopg environs while both
    #       coexist
    #
    group_id: int | None = await conn.scalar(
        sa.select(products.c.group_id)
        .where(products.c.name == product_name)
        .with_for_update(read=True)
        # a `FOR SHARE` lock: locks changes in the product until transaction is done.
        # Read might return in None, but it is OK
    )
    if group_id is None:
        group_id = await conn.scalar(
            groups.insert()
            .values(
                name=product_name,
                description=f"{product_name} product group",
                type=GroupType.STANDARD,
            )
            .returning(groups.c.gid)
        )
        assert group_id  # nosec

        await conn.execute(
            products.update()
            .where(products.c.name == product_name)
            .values(group_id=group_id)
        )

    return group_id
