# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

"""Tests the migration that creates `users_billing_details` and seeds it from the
most recent eligible pre-registration row (i.e. the one with `country` set) for
each already registered user.

testing
    packages/postgres-database/src/simcore_postgres_database/migration/versions/066e6a93b741_add_users_billing_details_table.py

revision = "066e6a93b741"
down_revision = "2962a102c124"

NOTE: at this migration point, the schemas of `users` and `users_pre_registration_details`
match the current models exactly (this migration only adds a new table), so the ORM
table objects can safely be used to insert the "before" data.
"""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
import simcore_postgres_database.cli
import sqlalchemy as sa
import sqlalchemy.engine
import sqlalchemy.exc
from faker import Faker
from pytest_simcore.helpers import postgres_tools
from pytest_simcore.helpers.faker_factories import (
    random_pre_registration_details,
    random_user,
)
from simcore_postgres_database.models.users import users
from simcore_postgres_database.models.users_details import users_pre_registration_details


@pytest.fixture
def sync_engine(sync_engine: sqlalchemy.engine.Engine, db_metadata: sa.MetaData) -> Iterator[sqlalchemy.engine.Engine]:
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


def test_users_billing_details_migration_seeds_from_pre_registration(
    sync_engine: sqlalchemy.engine.Engine, faker: Faker
):
    """
    SETUP SCENARIOS (per user, pre-registration rows ordered oldest -> newest):
    # user               | pre-registration rows (country, age)              | expected billing country
    user_one_row         | [CH @ -10d]                                       | CH
    user_newest_wins     | [FR @ -20d, DE @ -5d]                             | DE (most recent eligible)
    user_ineligible_last | [CH @ -15d, NULL @ -1d]                           | CH (newest has no country)
    user_no_country      | [NULL @ -1d]                                      | (none)
    user_no_pre_reg      | (no pre-registration rows at all)                | (none)
    user_unlinked_row    | (a pre-registration row exists but user_id NULL) | (none)
    """
    assert simcore_postgres_database.cli.upgrade.callback
    assert simcore_postgres_database.cli.downgrade.callback

    # UPGRADE just one before 066e6a93b741_add_users_billing_details_table.py
    simcore_postgres_database.cli.upgrade.callback("2962a102c124")

    with sync_engine.connect() as conn:
        # Ensure the users_billing_details table does NOT exist yet
        with pytest.raises(sqlalchemy.exc.ProgrammingError) as exc_info:
            conn.execute(sa.text("SELECT COUNT(*) FROM users_billing_details"))
        assert "psycopg2.errors.UndefinedTable" in f"{exc_info.value}"
        conn.rollback()

        def _insert_user(name: str) -> int:
            user_data = random_user(faker, name=name, email=f"{name}@example.com")
            return conn.execute(users.insert().returning(users.c.id), user_data).scalar_one()

        user_one_row_id = _insert_user("user_one_row")
        user_newest_wins_id = _insert_user("user_newest_wins")
        user_ineligible_last_id = _insert_user("user_ineligible_last")
        user_no_country_id = _insert_user("user_no_country")
        user_no_pre_reg_id = _insert_user("user_no_pre_reg")
        user_unlinked_row_id = _insert_user("user_unlinked_row")

        now = datetime.now(UTC).replace(tzinfo=None)  # naive: matches `created` column (timezone=False)

        def _insert_pre_registration(
            *, user_id: int | None, country: str | None, age: timedelta, pre_email: str
        ) -> None:
            pre_reg_data = random_pre_registration_details(
                faker,
                user_id=user_id,
                country=country,
                pre_email=pre_email,
                created=now - age,
            )
            conn.execute(users_pre_registration_details.insert(), pre_reg_data)

        # user_one_row: single eligible row
        _insert_pre_registration(
            user_id=user_one_row_id,
            country="Switzerland",
            age=timedelta(days=10),
            pre_email="user_one_row@example.com",
        )

        # user_newest_wins: two eligible rows, the most recent one must win
        _insert_pre_registration(
            user_id=user_newest_wins_id,
            country="France",
            age=timedelta(days=20),
            pre_email="user_newest_wins-older@example.com",
        )
        _insert_pre_registration(
            user_id=user_newest_wins_id,
            country="Germany",
            age=timedelta(days=5),
            pre_email="user_newest_wins-newer@example.com",
        )

        # user_ineligible_last: newest row has no country -> older eligible row wins
        _insert_pre_registration(
            user_id=user_ineligible_last_id,
            country="Switzerland",
            age=timedelta(days=15),
            pre_email="user_ineligible_last-older@example.com",
        )
        _insert_pre_registration(
            user_id=user_ineligible_last_id,
            country=None,
            age=timedelta(days=1),
            pre_email="user_ineligible_last-newer@example.com",
        )

        # user_no_country: only row has no country -> not eligible
        _insert_pre_registration(
            user_id=user_no_country_id,
            country=None,
            age=timedelta(days=1),
            pre_email="user_no_country@example.com",
        )

        # user_unlinked_row: pre-registration row not linked to any user
        _insert_pre_registration(
            user_id=None,
            country="Spain",
            age=timedelta(days=1),
            pre_email="user_unlinked_row@example.com",
        )

        conn.commit()

    # ACT: run the migration
    simcore_postgres_database.cli.upgrade.callback("066e6a93b741")

    # VERIFY
    with sync_engine.connect() as conn:
        result = conn.execute(sa.text("SELECT user_id, country FROM users_billing_details")).fetchall()
        country_by_user = {row.user_id: row.country for row in result}

        assert set(country_by_user) == {
            user_one_row_id,
            user_newest_wins_id,
            user_ineligible_last_id,
        }
        assert country_by_user[user_one_row_id] == "Switzerland"
        assert country_by_user[user_newest_wins_id] == "Germany"
        assert country_by_user[user_ineligible_last_id] == "Switzerland"

        assert user_no_country_id not in country_by_user
        assert user_no_pre_reg_id not in country_by_user
        assert user_unlinked_row_id not in country_by_user

    # DOWNGRADE
    simcore_postgres_database.cli.downgrade.callback("2962a102c124")

    with sync_engine.connect() as conn:
        # Verify users_billing_details table no longer exists
        with pytest.raises(sqlalchemy.exc.ProgrammingError) as exc_info:
            conn.execute(sa.text("SELECT COUNT(*) FROM users_billing_details"))
        assert "psycopg2.errors.UndefinedTable" in f"{exc_info.value}"
        conn.rollback()
