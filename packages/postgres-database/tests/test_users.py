# pylint: disable=no-value-for-parameter
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import json
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


async def test_user_status_as_pending(asyncpg_engine: AsyncEngine, faker: Faker, clean_users_db_table: None):
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
    asyncpg_engine: AsyncEngine,
    faker: Faker,
    clean_users_db_table: None,
):
    # insert as `status_value`
    data = random_user(faker, status=status_value)
    assert data["status"] == status_value

    async with transaction_context(asyncpg_engine) as connection:
        user_id = await connection.scalar(users.insert().values(data).returning(users.c.id))

        # get as UserStatus.CONFIRMATION_PENDING
        result = await connection.execute(users.select().where(users.c.id == user_id))
        user = result.one_or_none()
        assert user

        assert UserStatus(user.status) == UserStatus.CONFIRMATION_PENDING
        assert user.status == UserStatus.CONFIRMATION_PENDING


async def test_unique_username(asyncpg_engine: AsyncEngine, faker: Faker, clean_users_db_table: None):
    data = random_user(
        faker,
        status=UserStatus.ACTIVE,
        name="pcrespov",
        email="p@email.com",
        first_name="Pedro",
        last_name="Crespo Valero",
    )
    async with transaction_context(asyncpg_engine) as connection:
        user_id = await connection.scalar(users.insert().values(data).returning(users.c.id))
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


async def test_new_user(asyncpg_engine: AsyncEngine, faker: Faker, clean_users_db_table: None):
    data = {
        "email": faker.email(),
        "password_hash": "foo",
        "status": UserStatus.ACTIVE,
        "expires_at": datetime.utcnow(),  # noqa: DTZ003
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
        assert await repo.get_email(connection, user_id=other_user.id) == other_user.email
        assert await repo.get_role(connection, user_id=other_user.id) == other_user.role
        assert await repo.get_active_user_email(connection, user_id=other_user.id) == other_user.email


async def test_trial_accounts(asyncpg_engine: AsyncEngine, clean_users_db_table: None):
    EXPIRATION_INTERVAL = timedelta(minutes=5)

    # creates trial user
    client_now = datetime.utcnow()  # noqa: DTZ003
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
            sa.select(users.c.status, users.c.created_at, users.c.expires_at).where(users.c.id == user_id)
        )
        row = result.one_or_none()
        assert row
        assert row.created_at - client_now < timedelta(minutes=1), (
            "Difference between server and client now should not differ much"
        )
        assert row.expires_at - row.created_at == EXPIRATION_INTERVAL
        assert row.status == UserStatus.ACTIVE

        # sets user as expired
        await connection.execute(users.update().values(status=UserStatus.EXPIRED).where(users.c.id == user_id))


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


def test_users_secrets_migration_upgrade_downgrade(sync_engine_with_migration: sqlalchemy.engine.Engine, faker: Faker):
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
            conn.execute(sa.select(sa.func.count()).select_from(sa.table("users_secrets"))).scalar()
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
                "password_hash": "hashed_password_1",
            },
            {
                **random_user(
                    faker,
                    name="user_with_password_2",
                    email="user2@example.com",
                    role=UserRole.USER.value,
                    status=UserStatus.ACTIVE,
                ),
                "password_hash": "hashed_password_2",
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
        result = conn.execute(sa.text("SELECT user_id, password_hash FROM users_secrets ORDER BY user_id")).fetchall()

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


def test_pre_registration_reconciliation_migration_upgrade_downgrade(  # noqa: PLR0915
    sync_engine_with_migration: sqlalchemy.engine.Engine,
    faker: Faker,
):
    """Tests reconciliation migration for linked pre-registrations left in pending state.

    testing
        packages/postgres-database/src/simcore_postgres_database/migration/versions/7f8d9b1c2e4f_reconcile_linked_pending_pre_registrations.py

    revision = "7f8d9b1c2e4f"
    down_revision = "4c8dcaac4285"

    NOTE: all statements in conn.execute(...) must be sa.text(...) since at that migration point
          the schemas of the code models might not be the same

    SETUP SCENARIOS:
    # | user_id | status   | product | extras                       | created_by
    1 | NULL    | PENDING  | osparc  | {}                           | po_user
    2 | user_a  | PENDING  | osparc  | {invitation:{issuer,created}}| po_user
    3 | user_a  | PENDING  | s4l     | {}                           | po_user
    4 | user_b  | PENDING  | s4l     | {}                           | po_user
    5 | user_a  | REJECTED | osparc  | {}                           | po_user
    6 | user_a  | APPROVED | osparc  | {}                           | po_user

    1. New user, no link
    2. Linked + osparc access + invitation extras
    3. Linked, NO s4l access (user_a not in s4l group)
    4. Linked + s4l access (user_b), no invitation
    5. Already rejected
    6. Already approved

    EXPECTED AFTER MIGRATION UPGRADE:
    # | status   | reviewed_by          | reviewed_at       | recovery
    1 | PENDING  | NULL                 | NULL              | (none)
    2 | APPROVED | po_user (inv.issuer) | 2026-01 (inv)     | high
    3 | PENDING  | NULL                 | NULL              | (none)
    4 | APPROVED | NULL                 | user_b.created_at | medium
    5 | REJECTED | unchanged            | unchanged         | (none)
    6 | APPROVED | unchanged            | unchanged         | (none)
    """
    assert simcore_postgres_database.cli.upgrade.callback
    assert simcore_postgres_database.cli.downgrade.callback

    simcore_postgres_database.cli.upgrade.callback("4c8dcaac4285")

    # --- SETUP ---
    with sync_engine_with_migration.connect() as conn:
        # Users
        user_a_id = conn.execute(
            sa.text(
                "INSERT INTO users (name, email, role, status)"
                " VALUES (:name, :email, 'USER'::userrole, 'ACTIVE'::userstatus)"
                " RETURNING id"
            ),
            {"name": "user-a", "email": "user-a@example.com"},
        ).scalar_one()

        user_b_id = conn.execute(
            sa.text(
                "INSERT INTO users (name, email, role, status)"
                " VALUES (:name, :email, 'USER'::userrole, 'ACTIVE'::userstatus)"
                " RETURNING id"
            ),
            {"name": "user-b", "email": "user-b@example.com"},
        ).scalar_one()

        po_user_id = conn.execute(
            sa.text(
                "INSERT INTO users (name, email, role, status)"
                " VALUES (:name, :email, 'PRODUCT_OWNER'::userrole, 'ACTIVE'::userstatus)"
                " RETURNING id"
            ),
            {"name": "po-user", "email": "po-user@example.com"},
        ).scalar_one()

        # Capture user_b.created_at for later assertion (fallback for reviewed_at in scenario 4)
        user_b_created_at = conn.execute(
            sa.text("SELECT created_at FROM users WHERE id = :uid"),
            {"uid": user_b_id},
        ).scalar_one()

        # Groups for products
        osparc_group_id = conn.execute(
            sa.text(
                "INSERT INTO groups (name, description, type)"
                " VALUES ('osparc product group', 'osparc', 'STANDARD'::grouptype)"
                " RETURNING gid"
            ),
        ).scalar_one()

        s4l_group_id = conn.execute(
            sa.text(
                "INSERT INTO groups (name, description, type)"
                " VALUES ('s4l product group', 's4l', 'STANDARD'::grouptype)"
                " RETURNING gid"
            ),
        ).scalar_one()

        # Products: update osparc (already exists from prior migrations), insert s4l
        conn.execute(
            sa.text("UPDATE products SET group_id = :gid WHERE name = 'osparc'"),
            {"gid": osparc_group_id},
        )
        conn.execute(
            sa.text(
                "INSERT INTO products (name, host_regex, base_url, group_id)"
                " VALUES ('s4l', 's4l\\\\.example\\\\.com', 'https://s4l.example.com', :gid)"
            ),
            {"gid": s4l_group_id},
        )

        # Group membership: user_a -> osparc only, user_b -> osparc + s4l
        conn.execute(
            sa.text("INSERT INTO user_to_groups (uid, gid) VALUES (:uid, :gid)"),
            {"uid": user_a_id, "gid": osparc_group_id},
        )
        conn.execute(
            sa.text("INSERT INTO user_to_groups (uid, gid) VALUES (:uid, :gid)"),
            {"uid": user_b_id, "gid": osparc_group_id},
        )
        conn.execute(
            sa.text("INSERT INTO user_to_groups (uid, gid) VALUES (:uid, :gid)"),
            {"uid": user_b_id, "gid": s4l_group_id},
        )

        # --- PRE-REGISTRATION SCENARIOS ---

        _INSERT_PRE_REG = sa.text(
            "INSERT INTO users_pre_registration_details"
            " (user_id, pre_email, account_request_status, account_request_reviewed_by,"
            "  account_request_reviewed_at, product_name, created_by, extras)"
            " VALUES (:user_id, :pre_email, CAST(:status AS accountrequeststatus), :reviewed_by,"
            "  :reviewed_at, :product_name, :created_by, CAST(:extras AS jsonb))"
            " RETURNING id"
        )

        invitation_extras = json.dumps({"invitation": {"issuer": str(po_user_id), "created": "2026-01-01T00:00:00Z"}})

        # Scenario 1: New user, no link
        sc1_id = conn.execute(
            _INSERT_PRE_REG,
            {
                "user_id": None,
                "pre_email": "new-user@example.com",
                "status": "PENDING",
                "reviewed_by": None,
                "reviewed_at": None,
                "product_name": "osparc",
                "created_by": po_user_id,
                "extras": "{}",
            },
        ).scalar_one()

        # Scenario 2: Linked + osparc access + invitation extras
        sc2_id = conn.execute(
            _INSERT_PRE_REG,
            {
                "user_id": user_a_id,
                "pre_email": "user-a-osparc@example.com",
                "status": "PENDING",
                "reviewed_by": None,
                "reviewed_at": None,
                "product_name": "osparc",
                "created_by": po_user_id,
                "extras": invitation_extras,
            },
        ).scalar_one()

        # Scenario 3: Linked, NO s4l access (user_a is not in s4l group)
        sc3_id = conn.execute(
            _INSERT_PRE_REG,
            {
                "user_id": user_a_id,
                "pre_email": "user-a-s4l@example.com",
                "status": "PENDING",
                "reviewed_by": None,
                "reviewed_at": None,
                "product_name": "s4l",
                "created_by": po_user_id,
                "extras": "{}",
            },
        ).scalar_one()

        # Scenario 4: Linked + s4l access (user_b), no invitation
        sc4_id = conn.execute(
            _INSERT_PRE_REG,
            {
                "user_id": user_b_id,
                "pre_email": "user-b-s4l@example.com",
                "status": "PENDING",
                "reviewed_by": None,
                "reviewed_at": None,
                "product_name": "s4l",
                "created_by": po_user_id,
                "extras": "{}",
            },
        ).scalar_one()

        # Scenario 5: Already rejected
        sc5_id = conn.execute(
            _INSERT_PRE_REG,
            {
                "user_id": user_a_id,
                "pre_email": "rejected@example.com",
                "status": "REJECTED",
                "reviewed_by": po_user_id,
                "reviewed_at": datetime.utcnow(),  # noqa: DTZ003
                "product_name": "osparc",
                "created_by": po_user_id,
                "extras": "{}",
            },
        ).scalar_one()

        # Scenario 6: Already approved
        sc6_id = conn.execute(
            _INSERT_PRE_REG,
            {
                "user_id": user_a_id,
                "pre_email": "approved@example.com",
                "status": "APPROVED",
                "reviewed_by": po_user_id,
                "reviewed_at": datetime.utcnow(),  # noqa: DTZ003
                "product_name": "osparc",
                "created_by": po_user_id,
                "extras": "{}",
            },
        ).scalar_one()

    # --- ACT: run migration upgrade ---
    simcore_postgres_database.cli.upgrade.callback("7f8d9b1c2e4f")

    # --- VERIFY ---
    _SELECT_PRE_REG = sa.text(
        "SELECT account_request_status, account_request_reviewed_by,"
        " account_request_reviewed_at, extras"
        " FROM users_pre_registration_details WHERE id = :pid"
    )

    with sync_engine_with_migration.connect() as conn:
        # Scenario 1: untouched (no user_id)
        row1 = conn.execute(_SELECT_PRE_REG, {"pid": sc1_id}).one()
        assert row1.account_request_status == "PENDING"
        assert row1.account_request_reviewed_by is None
        assert row1.account_request_reviewed_at is None
        assert "recovery" not in (row1.extras or {})

        # Scenario 2: APPROVED, reviewer from invitation.issuer, reviewed_at from invitation.created
        row2 = conn.execute(_SELECT_PRE_REG, {"pid": sc2_id}).one()
        assert row2.account_request_status == "APPROVED"
        assert row2.account_request_reviewed_by == po_user_id
        assert row2.account_request_reviewed_at is not None
        # Verify recovery metadata
        assert "recovery" in row2.extras
        recovery2 = row2.extras["recovery"]
        assert recovery2["source"] == "migration:7f8d9b1c2e4f"
        assert recovery2["confidence"] == "high"
        assert recovery2["executed_at"] is not None
        assert "invitation issuer" in recovery2["notes"].lower()
        # Verify original invitation extras preserved
        assert "invitation" in row2.extras

        # Scenario 3: untouched (user_a not in s4l group)
        row3 = conn.execute(_SELECT_PRE_REG, {"pid": sc3_id}).one()
        assert row3.account_request_status == "PENDING"
        assert row3.account_request_reviewed_by is None
        assert row3.account_request_reviewed_at is None
        assert "recovery" not in (row3.extras or {})

        # Scenario 4: APPROVED, no invitation -> NULL reviewer, reviewed_at from user_b.created_at
        row4 = conn.execute(_SELECT_PRE_REG, {"pid": sc4_id}).one()
        assert row4.account_request_status == "APPROVED"
        assert row4.account_request_reviewed_by is None
        assert row4.account_request_reviewed_at is not None
        # reviewed_at should be user_b.created_at (fallback)
        reviewed_at = row4.account_request_reviewed_at
        if reviewed_at.tzinfo is not None:
            reviewed_at = reviewed_at.replace(tzinfo=None)
        expected_at = user_b_created_at
        if hasattr(expected_at, "tzinfo") and expected_at.tzinfo:
            expected_at = expected_at.replace(tzinfo=None)
        assert abs((reviewed_at - expected_at).total_seconds()) < 2
        # Verify recovery metadata
        assert "recovery" in row4.extras
        recovery4 = row4.extras["recovery"]
        assert recovery4["source"] == "migration:7f8d9b1c2e4f"
        assert recovery4["confidence"] == "medium"
        assert recovery4["executed_at"] is not None
        assert "no reviewer" in recovery4["notes"].lower()

        # Scenario 5: untouched (REJECTED)
        row5 = conn.execute(_SELECT_PRE_REG, {"pid": sc5_id}).one()
        assert row5.account_request_status == "REJECTED"
        assert row5.account_request_reviewed_by == po_user_id
        assert "recovery" not in (row5.extras or {})

        # Scenario 6: untouched (already APPROVED)
        row6 = conn.execute(_SELECT_PRE_REG, {"pid": sc6_id}).one()
        assert row6.account_request_status == "APPROVED"
        assert row6.account_request_reviewed_by == po_user_id
        assert "recovery" not in (row6.extras or {})

    # --- DOWNGRADE ---
    simcore_postgres_database.cli.downgrade.callback("4c8dcaac4285")
