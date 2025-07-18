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
            await repo.get_password_hash(connection, user_id=user["id"])
            == user["password_hash"]
        )
        assert (
            await repo.get_active_user_email(connection, user_id=user["id"])
            == user["email"]
        )

        with pytest.raises(UserNotFoundInRepoError):
            await repo.get_role(connection, user_id=55)
        with pytest.raises(UserNotFoundInRepoError):
            await repo.get_email(connection, user_id=55)
        with pytest.raises(UserNotFoundInRepoError):
            await repo.get_password_hash(connection, user_id=55)
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
                users_secrets.c.user_id == user["id"]
            )
        )
        initial_modified = result.scalar_one()

        # Update password hash
        new_password_hash = faker.password()
        await repo.update_user_password_hash(
            connection, user_id=user["id"], password_hash=new_password_hash
        )

        # Get updated modified timestamp
        result = await connection.execute(
            sa.select(users_secrets.c.modified).where(
                users_secrets.c.user_id == user["id"]
            )
        )
        updated_modified = result.scalar_one()

        # Verify modified timestamp changed
        assert updated_modified > initial_modified

        # Verify password hash was actually updated
        assert (
            await repo.get_password_hash(connection, user_id=user["id"])
            == new_password_hash
        )


async def test_update_user_password_hash_raises_when_user_not_found(
    asyncpg_engine: AsyncEngine, faker: Faker
):
    repo = UsersRepo(asyncpg_engine)

    async with pass_or_acquire_connection(asyncpg_engine) as connection:
        with pytest.raises(UserNotFoundInRepoError):
            await repo.update_user_password_hash(
                connection, user_id=999999, password_hash=faker.password()
            )
