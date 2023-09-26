# pylint: disable=no-value-for-parameter
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from datetime import datetime, timedelta

import pytest
import sqlalchemy as sa
from aiopg.sa.engine import Engine
from aiopg.sa.result import ResultProxy, RowProxy
from pytest_simcore.helpers.rawdata_fakers import random_user
from simcore_postgres_database.models.users import (
    _USER_ROLE_TO_LEVEL,
    FullNameTuple,
    UserNameConverter,
    UserRole,
    UserStatus,
    users,
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


async def test_trial_accounts(pg_engine: Engine):
    EXPIRATION_INTERVAL = timedelta(minutes=5)

    async with pg_engine.acquire() as conn:
        # creates trial user
        client_now = datetime.utcnow()
        user_id: int | None = await conn.scalar(
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
        result: ResultProxy = await conn.execute(
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
        await conn.execute(
            users.update()
            .values(status=UserStatus.EXPIRED)
            .where(users.c.id == user_id)
        )


@pytest.mark.parametrize(
    "first_name,last_name",
    [
        ("Erdem", "Ofli"),
        ("", "Ofli"),
        ("Erdem", ""),
        ("Dr. Erdem", "Ofli"),
        ("Erdem", "Ofli PhD."),
    ],
)
def test_user_name_conversions(first_name: str, last_name: str):
    # as 'update_user_profile'
    full_name = FullNameTuple(first_name, last_name)

    # gets name
    name = UserNameConverter.get_name(**full_name._asdict())

    # back to full_name
    assert UserNameConverter.get_full_name(name) == full_name
