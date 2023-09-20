from collections.abc import Iterable

import pytest
import sqlalchemy as sa
from models_library.users import UserID
from pytest_simcore.helpers.rawdata_fakers import random_user
from simcore_postgres_database.models.users import users


@pytest.fixture
def user_id(postgres_db: sa.engine.Engine) -> Iterable[UserID]:
    # inject user in db

    # NOTE: Ideally this (and next fixture) should be done via webserver API but at this point
    # in time, the webserver service would bring more dependencies to other services
    # which would turn this test too complex.

    # pylint: disable=no-value-for-parameter
    stmt = users.insert().values(**random_user(name="test")).returning(users.c.id)
    print(f"{stmt}")
    with postgres_db.connect() as conn:
        result = conn.execute(stmt)
        row = result.first()
        assert row
        usr_id = row[users.c.id]

    yield usr_id

    with postgres_db.connect() as conn:
        conn.execute(users.delete().where(users.c.id == usr_id))
