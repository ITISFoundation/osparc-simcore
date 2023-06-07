""" Common functions to access products table

"""

import sqlalchemy as sa

from ._protocols import AiopgConnection, DBConnection
from .models.groups import GroupType, groups
from .models.products import products

# NOTE: outside this module, use instead packages/models-library/src/models_library/users.py
_GroupID = int


async def get_default_product_name(conn: DBConnection) -> str:
    """The first row in the table is considered as the default product

    :: raises ValueError if undefined
    """
    product_name = await conn.scalar(
        sa.select(products.c.name).order_by(products.c.priority)
    )
    if not product_name:
        raise ValueError("No product defined in database")

    assert isinstance(product_name, str)  # nosec
    return product_name


async def get_product_group_id(
    connection: DBConnection, product_name: str
) -> _GroupID | None:
    group_id = await connection.scalar(
        sa.select(products.c.group_id).where(products.c.name == product_name)
    )
    return None if group_id is None else _GroupID(group_id)


async def get_or_create_product_group(
    connection: AiopgConnection, product_name: str
) -> _GroupID:
    """
    Returns group_id of a product. Creates it if undefined
    """
    async with connection.begin():
        group_id = await connection.scalar(
            sa.select(products.c.group_id)
            .where(products.c.name == product_name)
            .with_for_update(read=True)
            # a `FOR SHARE` lock: locks changes in the product until transaction is done.
            # Read might return in None, but it is OK
        )
        if group_id is None:
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

        return _GroupID(group_id)
