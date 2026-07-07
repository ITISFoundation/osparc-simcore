# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from collections.abc import AsyncIterable
from typing import Any

import pytest
import sqlalchemy as sa
from faker import Faker
from pytest_simcore.helpers.postgres_users import (
    insert_and_get_user_and_secrets_lifespan,
)
from simcore_postgres_database.models.users import UserRole
from simcore_postgres_database.models.users_secrets import users_secrets
from simcore_postgres_database.utils_repos import (
    pass_or_acquire_connection,
)
from simcore_postgres_database.utils_users import UserNotFoundInRepoError, UsersRepo
from sqlalchemy.ext.asyncio import AsyncEngine


@pytest.fixture
async def user(
    faker: Faker,
    asyncpg_engine: AsyncEngine,
) -> AsyncIterable[dict[str, Any]]:
    async with insert_and_get_user_and_secrets_lifespan(  # pylint:disable=contextmanager-generator-missing-cleanup
        asyncpg_engine,
        role=faker.random_element(elements=UserRole),
    ) as user_and_secrets_row:
        yield user_and_secrets_row


async def test_users_repo_get(asyncpg_engine: AsyncEngine, user: dict[str, Any]):
    repo = UsersRepo(asyncpg_engine)

    async with pass_or_acquire_connection(asyncpg_engine) as connection:
        assert await repo.get_email(connection, user_id=user["id"]) == user["email"]
        assert await repo.get_role(connection, user_id=user["id"]) == user["role"]
        assert (
            await repo.get_password_hash(connection, user_id=user["id"], product_name=user["product_name"])
            == user["password_hash"]
        )
        assert await repo.get_active_user_email(connection, user_id=user["id"]) == user["email"]

        with pytest.raises(UserNotFoundInRepoError):
            await repo.get_role(connection, user_id=55)
        with pytest.raises(UserNotFoundInRepoError):
            await repo.get_email(connection, user_id=55)
        with pytest.raises(UserNotFoundInRepoError):
            await repo.get_password_hash(connection, user_id=55, product_name=user["product_name"])
        with pytest.raises(UserNotFoundInRepoError):
            await repo.get_active_user_email(connection, user_id=55)


async def test_update_user_password_hash_updates_modified_column(
    asyncpg_engine: AsyncEngine, user: dict[str, Any], faker: Faker
):
    repo = UsersRepo(asyncpg_engine)

    async with pass_or_acquire_connection(asyncpg_engine) as connection:
        # Get initial modified timestamp
        result = await connection.execute(
            sa.select(users_secrets.c.modified).where(
                (users_secrets.c.user_id == user["id"]) & (users_secrets.c.product_name == user["product_name"])
            )
        )
        initial_modified = result.scalar_one()

        # Update password hash
        new_password_hash = faker.password()
        await repo.update_user_password_hash(
            connection, user_id=user["id"], product_name=user["product_name"], password_hash=new_password_hash
        )

        # Get updated modified timestamp
        result = await connection.execute(
            sa.select(users_secrets.c.modified).where(
                (users_secrets.c.user_id == user["id"]) & (users_secrets.c.product_name == user["product_name"])
            )
        )
        updated_modified = result.scalar_one()

        # Verify modified timestamp changed
        assert updated_modified > initial_modified

        # Verify password hash was actually updated
        assert (
            await repo.get_password_hash(connection, user_id=user["id"], product_name=user["product_name"])
            == new_password_hash
        )


async def test_get_password_hash_falls_back_to_osparc_and_copies_it(
    asyncpg_engine: AsyncEngine, user: dict[str, Any], create_fake_product: Any
):
    """user fixture only has a password for 'osparc' (the default). Accessing another
    product should fall back to the osparc password hash and persist a copy for that product."""
    repo = UsersRepo(asyncpg_engine)
    other_product = await create_fake_product("other-product")

    async with pass_or_acquire_connection(asyncpg_engine) as connection:
        # no row yet for "other-product"
        result = await connection.execute(
            sa.select(users_secrets.c.password_hash).where(
                (users_secrets.c.user_id == user["id"]) & (users_secrets.c.product_name == other_product["name"])
            )
        )
        assert result.one_or_none() is None

        hash_from_fallback = await repo.get_password_hash(
            connection, user_id=user["id"], product_name=other_product["name"]
        )
        assert hash_from_fallback == user["password_hash"]

        # a row now exists for "other-product" with the copied hash
        result = await connection.execute(
            sa.select(users_secrets.c.password_hash).where(
                (users_secrets.c.user_id == user["id"]) & (users_secrets.c.product_name == other_product["name"])
            )
        )
        assert result.scalar_one() == user["password_hash"]


async def test_update_user_password_hash_does_not_propagate_to_other_products(
    asyncpg_engine: AsyncEngine, user: dict[str, Any], create_fake_product: Any, faker: Faker
):
    repo = UsersRepo(asyncpg_engine)
    other_product = await create_fake_product("other-product")

    # trigger fallback+copy for "other-product"
    await repo.get_password_hash(user_id=user["id"], product_name=other_product["name"])

    # update password only for the original ("osparc") product
    new_password_hash = faker.password()
    await repo.update_user_password_hash(
        user_id=user["id"], product_name=user["product_name"], password_hash=new_password_hash
    )

    assert await repo.get_password_hash(user_id=user["id"], product_name=user["product_name"]) == new_password_hash
    # other product's row is untouched
    assert await repo.get_password_hash(user_id=user["id"], product_name=other_product["name"]) == user["password_hash"]
