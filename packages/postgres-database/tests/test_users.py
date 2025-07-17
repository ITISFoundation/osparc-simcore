# pylint: disable=no-value-for-parameter
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from datetime import datetime, timedelta

import pytest
import sqlalchemy as sa
from faker import Faker
from pytest_simcore.helpers.faker_factories import random_user
from simcore_postgres_database.models.users import UserRole, UserStatus, users
from simcore_postgres_database.utils_repos import (
    pass_or_acquire_connection,
    transaction_context,
)
from simcore_postgres_database.utils_users import (
    UsersRepo,
    _generate_username_from_email,
    generate_alternative_username,
)
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.sql import func


@pytest.fixture
async def clean_users_db_table(asyncpg_engine: AsyncEngine):
    yield
    async with transaction_context(asyncpg_engine) as connection:
        await connection.execute(users.delete())


async def test_user_status_as_pending(
    asyncpg_engine: AsyncEngine, faker: Faker, clean_users_db_table: None
):
    """Checks a bug where the expression

        `user_status = UserStatus(user["status"])`

    raise ValueError because **before** this change `UserStatus.CONFIRMATION_PENDING.value == "PENDING"`
    """
    # after changing to UserStatus.CONFIRMATION_PENDING == "CONFIRMATION_PENDING"
    with pytest.raises(ValueError):  # noqa: PT011
        assert UserStatus("PENDING") == UserStatus.CONFIRMATION_PENDING

    assert UserStatus("CONFIRMATION_PENDING") == UserStatus.CONFIRMATION_PENDING
    assert UserStatus.CONFIRMATION_PENDING.value == "CONFIRMATION_PENDING"
    assert UserStatus.CONFIRMATION_PENDING == "CONFIRMATION_PENDING"
    assert str(UserStatus.CONFIRMATION_PENDING) == "UserStatus.CONFIRMATION_PENDING"

    # tests that the database never stores the word "PENDING"
    data = random_user(faker, status="PENDING")
    assert data["status"] == "PENDING"
    async with transaction_context(asyncpg_engine) as connection:
        with pytest.raises(DBAPIError) as err_info:
            await connection.execute(users.insert().values(data))

        assert (
            'invalid input value for enum userstatus: "PENDING"' in f"{err_info.value}"
        )


@pytest.mark.parametrize(
    "status_value",
    [
        UserStatus.CONFIRMATION_PENDING,
        "CONFIRMATION_PENDING",
    ],
)
async def test_user_status_inserted_as_enum_or_int(
    status_value: UserStatus | str,
    asyncpg_engine: AsyncEngine,
    faker: Faker,
    clean_users_db_table: None,
):
    # insert as `status_value`
    data = random_user(faker, status=status_value)
    assert data["status"] == status_value

    async with transaction_context(asyncpg_engine) as connection:
        user_id = await connection.scalar(
            users.insert().values(data).returning(users.c.id)
        )

        # get as UserStatus.CONFIRMATION_PENDING
        result = await connection.execute(users.select().where(users.c.id == user_id))
        user = result.one_or_none()
        assert user

        assert UserStatus(user.status) == UserStatus.CONFIRMATION_PENDING
        assert user.status == UserStatus.CONFIRMATION_PENDING


async def test_unique_username(
    asyncpg_engine: AsyncEngine, faker: Faker, clean_users_db_table: None
):
    data = random_user(
        faker,
        status=UserStatus.ACTIVE,
        name="pcrespov",
        email="p@email.com",
        first_name="Pedro",
        last_name="Crespo Valero",
    )
    async with transaction_context(asyncpg_engine) as connection:
        user_id = await connection.scalar(
            users.insert().values(data).returning(users.c.id)
        )
        result = await connection.execute(users.select().where(users.c.id == user_id))
        user = result.one_or_none()
        assert user

        assert user.id == user_id
        assert user.name == "pcrespov"

    async with transaction_context(asyncpg_engine) as connection:
        # same name fails
        data["email"] = faker.email()
        with pytest.raises(IntegrityError):
            await connection.scalar(users.insert().values(data).returning(users.c.id))

    async with transaction_context(asyncpg_engine) as connection:
        # generate new name
        data["name"] = _generate_username_from_email(user.email)
        data["email"] = faker.email()
        await connection.scalar(users.insert().values(data).returning(users.c.id))

    async with transaction_context(asyncpg_engine) as connection:

        # and another one
        data["name"] = generate_alternative_username(data["name"])
        data["email"] = faker.email()
        await connection.scalar(users.insert().values(data).returning(users.c.id))


async def test_new_user(
    asyncpg_engine: AsyncEngine, faker: Faker, clean_users_db_table: None
):
    data = {
        "email": faker.email(),
        "password_hash": "foo",
        "status": UserStatus.ACTIVE,
        "expires_at": datetime.utcnow(),
    }
    repo = UsersRepo(asyncpg_engine)
    new_user = await repo.new_user(**data)

    assert new_user.email == data["email"]
    assert new_user.status == data["status"]
    assert new_user.role == UserRole.USER

    other_email = f"{new_user.name}@other-domain.com"
    assert _generate_username_from_email(other_email) == new_user.name
    other_data = {**data, "email": other_email}

    other_user = await repo.new_user(**other_data)
    assert other_user.email != new_user.email
    assert other_user.name != new_user.name

    async with pass_or_acquire_connection(asyncpg_engine) as connection:
        assert (
            await repo.get_email(connection, user_id=other_user.id) == other_user.email
        )
        assert await repo.get_role(connection, user_id=other_user.id) == other_user.role
        assert (
            await repo.get_active_user_email(connection, user_id=other_user.id)
            == other_user.email
        )


async def test_trial_accounts(asyncpg_engine: AsyncEngine, clean_users_db_table: None):
    EXPIRATION_INTERVAL = timedelta(minutes=5)

    # creates trial user
    client_now = datetime.utcnow()
    async with transaction_context(asyncpg_engine) as connection:
        user_id: int | None = await connection.scalar(
            users.insert()
            .values(
                **random_user(
                    status=UserStatus.ACTIVE,
                    # Using some magic from sqlachemy ...
                    expires_at=func.now() + EXPIRATION_INTERVAL,
                )
            )
            .returning(users.c.id)
        )
        assert user_id

        # check expiration date
        result = await connection.execute(
            sa.select(users.c.status, users.c.created_at, users.c.expires_at).where(
                users.c.id == user_id
            )
        )
        row = result.one_or_none()
        assert row
        assert row.created_at - client_now < timedelta(
            minutes=1
        ), "Difference between server and client now should not differ much"
        assert row.expires_at - row.created_at == EXPIRATION_INTERVAL
        assert row.status == UserStatus.ACTIVE

        # sets user as expired
        await connection.execute(
            users.update()
            .values(status=UserStatus.EXPIRED)
            .where(users.c.id == user_id)
        )
