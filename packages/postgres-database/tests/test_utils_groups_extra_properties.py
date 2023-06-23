# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

from typing import Awaitable, Callable

import aiopg.sa
import pytest
import sqlalchemy
from aiopg.sa.result import RowProxy
from faker import Faker
from simcore_postgres_database.models.groups_extra_properties import (
    groups_extra_properties,
)
from simcore_postgres_database.models.products import products
from simcore_postgres_database.utils_groups_extra_properties import (
    GroupExtraProperties,
    GroupExtraPropertiesNotFound,
    GroupExtraPropertiesRepo,
)
from sqlalchemy import literal_column


async def test_get_raises_if_not_found(
    faker: Faker, connection: aiopg.sa.connection.SAConnection
):
    with pytest.raises(GroupExtraPropertiesNotFound):
        await GroupExtraPropertiesRepo.get(
            connection, gid=faker.pyint(min_value=1), product_name=faker.pystr()
        )


@pytest.fixture
async def registered_user(
    connection: aiopg.sa.connection.SAConnection,
    create_fake_user: Callable[..., Awaitable[RowProxy]],
):
    return await create_fake_user(connection)


@pytest.fixture
def product_name(faker: Faker) -> str:
    return faker.pystr()


@pytest.fixture
def create_fake_product(
    connection: aiopg.sa.connection.SAConnection,
) -> Callable[..., Awaitable[RowProxy]]:
    async def _creator(product_name: str) -> RowProxy:
        result = await connection.execute(
            sqlalchemy.insert(products)
            .values(name=product_name, host_regex=".*")
            .returning(literal_column("*"))
        )
        assert result
        row = await result.first()
        assert row
        return row

    return _creator


@pytest.fixture
def create_fake_group_extra_properties(
    connection: aiopg.sa.connection.SAConnection,
) -> Callable[..., Awaitable[GroupExtraProperties]]:
    async def _creator(gid: int, product_name: str) -> GroupExtraProperties:
        result = await connection.execute(
            sqlalchemy.insert(groups_extra_properties)
            .values(group_id=gid, product_name=product_name)
            .returning(literal_column("*"))
        )
        assert result
        row = await result.first()
        assert row
        return GroupExtraProperties.from_row(row)

    return _creator


async def test_get(
    connection: aiopg.sa.connection.SAConnection,
    registered_user: RowProxy,
    product_name: str,
    create_fake_product: Callable[..., Awaitable[RowProxy]],
    create_fake_group_extra_properties: Callable[..., Awaitable[GroupExtraProperties]],
):
    with pytest.raises(GroupExtraPropertiesNotFound):
        await GroupExtraPropertiesRepo.get(
            connection, gid=registered_user.primary_gid, product_name=product_name
        )

    await create_fake_product(product_name)
    created_extra_properties = await create_fake_group_extra_properties(
        registered_user.primary_gid, product_name
    )
    received_extra_properties = await GroupExtraPropertiesRepo.get(
        connection, gid=registered_user.primary_gid, product_name=product_name
    )
    assert created_extra_properties == received_extra_properties
