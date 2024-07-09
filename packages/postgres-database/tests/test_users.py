# pylint: disable=no-value-for-parameter
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from datetime import datetime, timedelta

import pytest
import sqlalchemy as sa
from aiopg.sa.connection import SAConnection
from aiopg.sa.result import ResultProxy, RowProxy
from faker import Faker
from pytest_simcore.helpers.faker_factories import random_user
from simcore_postgres_database.errors import InvalidTextRepresentation, UniqueViolation
from simcore_postgres_database.models.users import (
    _USER_ROLE_TO_LEVEL,
    UserRole,
    UserStatus,
    users,
)
from simcore_postgres_database.utils_users import (
    UsersRepo,
    _generate_random_chars,
    _generate_username_from_email,
)
from sqlalchemy.sql import func


def test_user_role_to_level_map_in_sync():
    # If fails, then update _USER_ROLE_TO_LEVEL map
    assert set(_USER_ROLE_TO_LEVEL.keys()) == set(UserRole.__members__.keys())


def test_user_roles_compares_to_admin():
    assert UserRole.ANONYMOUS < UserRole.ADMIN
    assert UserRole.GUEST < UserRole.ADMIN
    assert UserRole.USER < UserRole.ADMIN
    assert UserRole.TESTER < UserRole.ADMIN
    assert UserRole.PRODUCT_OWNER < UserRole.ADMIN
    assert UserRole.ADMIN == UserRole.ADMIN


def test_user_roles_compares_to_product_owner():
    assert UserRole.ANONYMOUS < UserRole.PRODUCT_OWNER
    assert UserRole.GUEST < UserRole.PRODUCT_OWNER
    assert UserRole.USER < UserRole.PRODUCT_OWNER
    assert UserRole.TESTER < UserRole.PRODUCT_OWNER
    assert UserRole.PRODUCT_OWNER == UserRole.PRODUCT_OWNER
    assert UserRole.ADMIN > UserRole.PRODUCT_OWNER


def test_user_roles_compares_to_tester():
    assert UserRole.ANONYMOUS < UserRole.TESTER
    assert UserRole.GUEST < UserRole.TESTER
    assert UserRole.USER < UserRole.TESTER
    assert UserRole.TESTER == UserRole.TESTER
    assert UserRole.PRODUCT_OWNER > UserRole.TESTER
    assert UserRole.ADMIN > UserRole.TESTER


def test_user_roles_compares_to_user():
    assert UserRole.ANONYMOUS < UserRole.USER
    assert UserRole.GUEST < UserRole.USER
    assert UserRole.USER == UserRole.USER
    assert UserRole.TESTER > UserRole.USER
    assert UserRole.PRODUCT_OWNER > UserRole.USER
    assert UserRole.ADMIN > UserRole.USER


def test_user_roles_compares_to_guest():
    assert UserRole.ANONYMOUS < UserRole.GUEST
    assert UserRole.GUEST == UserRole.GUEST
    assert UserRole.USER > UserRole.GUEST
    assert UserRole.TESTER > UserRole.GUEST
    assert UserRole.PRODUCT_OWNER > UserRole.GUEST
    assert UserRole.ADMIN > UserRole.GUEST


def test_user_roles_compares_to_anonymous():
    assert UserRole.ANONYMOUS == UserRole.ANONYMOUS
    assert UserRole.GUEST > UserRole.ANONYMOUS
    assert UserRole.USER > UserRole.ANONYMOUS
    assert UserRole.TESTER > UserRole.ANONYMOUS
    assert UserRole.PRODUCT_OWNER > UserRole.ANONYMOUS
    assert UserRole.ADMIN > UserRole.ANONYMOUS


def test_user_roles_compares():
    # < and >
    assert UserRole.TESTER < UserRole.ADMIN
    assert UserRole.ADMIN > UserRole.TESTER

    # >=, == and <=
    assert UserRole.TESTER <= UserRole.ADMIN
    assert UserRole.ADMIN >= UserRole.TESTER

    assert UserRole.ADMIN <= UserRole.ADMIN
    assert UserRole.ADMIN == UserRole.ADMIN


@pytest.fixture
async def clean_users_db_table(connection: SAConnection):
    yield
    await connection.execute(users.delete())


async def test_user_status_as_pending(
    connection: SAConnection, faker: Faker, clean_users_db_table: None
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
    with pytest.raises(InvalidTextRepresentation) as err_info:
        await connection.execute(users.insert().values(data))

    assert 'invalid input value for enum userstatus: "PENDING"' in f"{err_info.value}"


@pytest.mark.parametrize(
    "status_value",
    [
        UserStatus.CONFIRMATION_PENDING,
        "CONFIRMATION_PENDING",
    ],
)
async def test_user_status_inserted_as_enum_or_int(
    status_value: UserStatus | str,
    connection: SAConnection,
    faker: Faker,
    clean_users_db_table: None,
):
    # insert as `status_value`
    data = random_user(faker, status=status_value)
    assert data["status"] == status_value
    user_id = await connection.scalar(users.insert().values(data).returning(users.c.id))

    # get as UserStatus.CONFIRMATION_PENDING
    user = await (
        await connection.execute(users.select().where(users.c.id == user_id))
    ).first()
    assert user

    assert UserStatus(user.status) == UserStatus.CONFIRMATION_PENDING
    assert user.status == UserStatus.CONFIRMATION_PENDING


async def test_unique_username(
    connection: SAConnection, faker: Faker, clean_users_db_table: None
):
    data = random_user(
        faker,
        status=UserStatus.ACTIVE,
        name="pcrespov",
        email="some-fanky-name@email.com",
        first_name="Pedro",
        last_name="Crespo Valero",
    )
    user_id = await connection.scalar(users.insert().values(data).returning(users.c.id))
    user = await (
        await connection.execute(users.select().where(users.c.id == user_id))
    ).first()
    assert user

    assert user.id == user_id
    assert user.name == "pcrespov"

    # same name fails
    data["email"] = faker.email()
    with pytest.raises(UniqueViolation):
        await connection.scalar(users.insert().values(data).returning(users.c.id))

    # generate new name
    data["name"] = _generate_username_from_email(user.email)
    data["email"] = faker.email()
    await connection.scalar(users.insert().values(data).returning(users.c.id))

    # and another one
    data["name"] += _generate_random_chars()
    data["email"] = faker.email()
    await connection.scalar(users.insert().values(data).returning(users.c.id))


async def test_new_user(
    connection: SAConnection, faker: Faker, clean_users_db_table: None
):
    data = {
        "email": faker.email(),
        "password_hash": "foo",
        "status": UserStatus.ACTIVE,
        "expires_at": datetime.utcnow(),
    }
    new_user = await UsersRepo.new_user(connection, **data)

    assert new_user.email == data["email"]
    assert new_user.status == data["status"]
    assert new_user.role == UserRole.USER

    other_email = f"{new_user.name}@other-domain.com"
    assert _generate_username_from_email(other_email) == new_user.name
    other_data = {**data, "email": other_email}

    other_user = await UsersRepo.new_user(connection, **other_data)
    assert other_user.email != new_user.email
    assert other_user.name != new_user.name

    assert await UsersRepo.get_email(connection, other_user.id) == other_user.email
    assert await UsersRepo.get_role(connection, other_user.id) == other_user.role
    assert (
        await UsersRepo.get_active_user_email(connection, other_user.id)
        == other_user.email
    )


async def test_trial_accounts(connection: SAConnection, clean_users_db_table: None):
    EXPIRATION_INTERVAL = timedelta(minutes=5)

    # creates trial user
    client_now = datetime.utcnow()
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
    result: ResultProxy = await connection.execute(
        sa.select(users.c.status, users.c.created_at, users.c.expires_at).where(
            users.c.id == user_id
        )
    )
    row: RowProxy | None = await result.first()
    assert row
    assert row.created_at - client_now < timedelta(
        minutes=1
    ), "Difference between server and client now should not differ much"
    assert row.expires_at - row.created_at == EXPIRATION_INTERVAL
    assert row.status == UserStatus.ACTIVE

    # sets user as expired
    await connection.execute(
        users.update().values(status=UserStatus.EXPIRED).where(users.c.id == user_id)
    )
