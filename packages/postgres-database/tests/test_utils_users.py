# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from collections.abc import AsyncIterable
from typing import Any

import pytest
from faker import Faker
from pytest_simcore.helpers.faker_factories import (
    random_user,
)
from pytest_simcore.helpers.postgres_tools import (
    insert_and_get_row_lifespan,
)
from simcore_postgres_database.models.users import UserRole, users
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
    async with insert_and_get_row_lifespan(  # pylint:disable=contextmanager-generator-missing-cleanup
        asyncpg_engine,
        table=users,
        values=random_user(
            faker,
            role=faker.random_element(elements=UserRole),
        ),
        pk_col=users.c.id,
    ) as row:
        yield row


async def test_users_repo_get(asyncpg_engine: AsyncEngine, user: dict[str, Any]):
    repo = UsersRepo()

    async with pass_or_acquire_connection(asyncpg_engine) as connection:
        assert await repo.get_email(connection, user_id=user["id"]) == user["email"]
        assert await repo.get_role(connection, user_id=user["id"]) == user["role"]

        with pytest.raises(UserNotFoundInRepoError):
            await repo.get_role(connection, user_id=55)
