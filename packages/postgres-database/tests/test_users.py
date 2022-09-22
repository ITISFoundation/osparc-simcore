from datetime import datetime, timedelta
from typing import Optional

import sqlalchemy as sa
from aiopg.sa.engine import Engine
from aiopg.sa.result import ResultProxy, RowProxy
from pytest_simcore.helpers.rawdata_fakers import random_user
from simcore_postgres_database.models.users import (
    _USER_ROLE_TO_LEVEL,
    UserRole,
    UserStatus,
    users,
)
from sqlalchemy.sql import func


def test_user_role_to_level_map_in_sync():
    # If fails, then update _USER_ROLE_TO_LEVEL map
    assert set(_USER_ROLE_TO_LEVEL.keys()) == set(UserRole.__members__.keys())


def test_user_role_comparison():

    assert UserRole.ANONYMOUS < UserRole.ADMIN
    assert UserRole.GUEST < UserRole.ADMIN
    assert UserRole.USER < UserRole.ADMIN
    assert UserRole.TESTER < UserRole.ADMIN
    assert UserRole.ADMIN == UserRole.ADMIN

    assert UserRole.ANONYMOUS < UserRole.TESTER
    assert UserRole.GUEST < UserRole.TESTER
    assert UserRole.USER < UserRole.TESTER
    assert UserRole.TESTER == UserRole.TESTER
    assert UserRole.ADMIN > UserRole.TESTER

    assert UserRole.ANONYMOUS < UserRole.USER
    assert UserRole.GUEST < UserRole.USER
    assert UserRole.USER == UserRole.USER
    assert UserRole.TESTER > UserRole.USER
    assert UserRole.ADMIN > UserRole.USER

    assert UserRole.ANONYMOUS < UserRole.GUEST
    assert UserRole.GUEST == UserRole.GUEST
    assert UserRole.USER > UserRole.GUEST
    assert UserRole.TESTER > UserRole.GUEST
    assert UserRole.ADMIN > UserRole.GUEST

    assert UserRole.ANONYMOUS == UserRole.ANONYMOUS
    assert UserRole.GUEST > UserRole.ANONYMOUS
    assert UserRole.USER > UserRole.ANONYMOUS
    assert UserRole.TESTER > UserRole.ANONYMOUS
    assert UserRole.ADMIN > UserRole.ANONYMOUS

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
        user_id: Optional[int] = await conn.scalar(
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
            sa.select([users.c.status, users.c.created_at, users.c.expires_at]).where(
                users.c.id == user_id
            )
        )
        row: Optional[RowProxy] = await result.first()
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
