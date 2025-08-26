# pylint: disable=no-value-for-parameter
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from collections.abc import Iterator
from datetime import datetime, timedelta

import pytest
import simcore_postgres_database.cli
import sqlalchemy as sa
import sqlalchemy.engine
import sqlalchemy.exc
from faker import Faker
from pytest_simcore.helpers import postgres_tools
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


@pytest.fixture
def sync_engine_with_migration(
    sync_engine: sqlalchemy.engine.Engine, db_metadata: sa.MetaData
) -> Iterator[sqlalchemy.engine.Engine]:
    # EXTENDS sync_engine fixture to include cleanup and prepare migration

    # cleanup tables
    db_metadata.drop_all(sync_engine)

    # prepare migration upgrade
    assert simcore_postgres_database.cli.discover.callback
    assert simcore_postgres_database.cli.upgrade.callback

    dsn = sync_engine.url
    simcore_postgres_database.cli.discover.callback(
        user=dsn.username,
        password=dsn.password,
        host=dsn.host,
        database=dsn.database,
        port=dsn.port,
    )

    yield sync_engine

    # cleanup tables
    postgres_tools.force_drop_all_tables(sync_engine)


def test_users_secrets_migration_upgrade_downgrade(
    sync_engine_with_migration: sqlalchemy.engine.Engine, faker: Faker
):
    """Tests the migration script that moves password_hash from users to users_secrets table.


    testing
        packages/postgres-database/src/simcore_postgres_database/migration/versions/5679165336c8_new_users_secrets.py

    revision = "5679165336c8"
    down_revision = "61b98a60e934"


    NOTE: all statements in conn.execute(...) must be sa.text(...) since at that migration point the schemas of the
         code models might not be the same
    """
    assert simcore_postgres_database.cli.discover.callback
    assert simcore_postgres_database.cli.upgrade.callback
    assert simcore_postgres_database.cli.downgrade.callback

    # UPGRADE just one before 5679165336c8_new_users_secrets.py
    simcore_postgres_database.cli.upgrade.callback("61b98a60e934")

    with sync_engine_with_migration.connect() as conn:
        # Ensure the users_secrets table does NOT exist yet
        with pytest.raises(sqlalchemy.exc.ProgrammingError) as exc_info:
            conn.execute(
                sa.select(sa.func.count()).select_from(sa.table("users_secrets"))
            ).scalar()
        assert "psycopg2.errors.UndefinedTable" in f"{exc_info.value}"

        # INSERT users with password hashes (emulates data in-place before migration)
        users_data_with_hashed_password = [
            {
                **random_user(
                    faker,
                    name="user_with_password_1",
                    email="user1@example.com",
                    role=UserRole.USER.value,
                    status=UserStatus.ACTIVE,
                ),
                "password_hash": "hashed_password_1",  # noqa: S106
            },
            {
                **random_user(
                    faker,
                    name="user_with_password_2",
                    email="user2@example.com",
                    role=UserRole.USER.value,
                    status=UserStatus.ACTIVE,
                ),
                "password_hash": "hashed_password_2",  # noqa: S106
            },
        ]

        inserted_user_ids = []
        for user_data in users_data_with_hashed_password:
            columns = ", ".join(user_data.keys())
            values_placeholders = ", ".join(f":{key}" for key in user_data)
            user_id = conn.execute(
                sa.text(
                    f"INSERT INTO users ({columns}) VALUES ({values_placeholders}) RETURNING id"  # noqa: S608
                ),
                user_data,
            ).scalar()
            inserted_user_ids.append(user_id)

        # Verify password hashes are in users table
        result = conn.execute(
            sa.text("SELECT id, password_hash FROM users WHERE id = ANY(:user_ids)"),
            {"user_ids": inserted_user_ids},
        ).fetchall()

        password_hashes_before = {row.id: row.password_hash for row in result}
        assert len(password_hashes_before) == 2
        assert password_hashes_before[inserted_user_ids[0]] == "hashed_password_1"
        assert password_hashes_before[inserted_user_ids[1]] == "hashed_password_2"

    # MIGRATE UPGRADE: this should move password hashes to users_secrets
    # packages/postgres-database/src/simcore_postgres_database/migration/versions/5679165336c8_new_users_secrets.py
    simcore_postgres_database.cli.upgrade.callback("5679165336c8")

    with sync_engine_with_migration.connect() as conn:
        # Verify users_secrets table exists and contains the password hashes
        result = conn.execute(
            sa.text("SELECT user_id, password_hash FROM users_secrets ORDER BY user_id")
        ).fetchall()

        # Only users with non-null password hashes should be in users_secrets
        assert len(result) == 2
        secrets_data = {row.user_id: row.password_hash for row in result}
        assert secrets_data[inserted_user_ids[0]] == "hashed_password_1"
        assert secrets_data[inserted_user_ids[1]] == "hashed_password_2"

        # Verify password_hash column is removed from users table
        with pytest.raises(sqlalchemy.exc.ProgrammingError) as exc_info:
            conn.execute(sa.text("SELECT password_hash FROM users"))
        assert "psycopg2.errors.UndefinedColumn" in f"{exc_info.value}"

    # MIGRATE DOWNGRADE: this should move password hashes back to users
    simcore_postgres_database.cli.downgrade.callback("61b98a60e934")

    with sync_engine_with_migration.connect() as conn:
        # Verify users_secrets table no longer exists
        with pytest.raises(sqlalchemy.exc.ProgrammingError) as exc_info:
            conn.execute(sa.text("SELECT COUNT(*) FROM users_secrets")).scalar()
        assert "psycopg2.errors.UndefinedTable" in f"{exc_info.value}"

        # Verify password hashes are back in users table
        result = conn.execute(
            sa.text("SELECT id, password_hash FROM users WHERE id = ANY(:user_ids)"),
            {"user_ids": inserted_user_ids},
        ).fetchall()

        password_hashes_after = {row.id: row.password_hash for row in result}
        assert len(password_hashes_after) == 2
        assert password_hashes_after[inserted_user_ids[0]] == "hashed_password_1"
        assert password_hashes_after[inserted_user_ids[1]] == "hashed_password_2"
