# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from typing import Any

import pytest
from aiopg.sa.connection import SAConnection
from faker import Faker
from pytest_simcore.helpers.faker_factories import random_user
from simcore_postgres_database.models.users import UserRole, users
from simcore_postgres_database.utils_users import UserNotFoundInRepoError, UsersRepo


@pytest.fixture
async def user(connection: SAConnection, faker: Faker) -> dict[str, Any]:
    data = random_user(role=faker.random_element(elements=UserRole))
    user_id = await connection.scalar(
        users.insert().values(**data).returning(users.c.id)
    )
    assert user_id
    data["id"] = user_id
    return data


async def test_users_repo_get(connection: SAConnection, user: dict[str, Any]):
    repo = UsersRepo()

    assert await repo.get_email(connection, user_id=user["id"]) == user["email"]
    assert await repo.get_role(connection, user_id=user["id"]) == user["role"]

    with pytest.raises(UserNotFoundInRepoError):
        await repo.get_role(connection, user_id=55)
