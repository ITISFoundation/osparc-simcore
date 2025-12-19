# pylint: disable=no-value-for-parameter
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import sqlalchemy as sa
from simcore_postgres_database.models.users import users
from simcore_postgres_database.utils import (
    as_postgres_sql_query_str,
    hide_dict_pass,
    hide_url_pass,
)
from yarl import URL


def test_hide_url_pass():
    assert (
        hide_url_pass(URL("postgres://username:password@127.0.0.1/myrailsdb"))
        == "postgres://username:********@127.0.0.1/myrailsdb"
    )


def test_hide_dict_pass():
    assert hide_dict_pass({"pass": "foo", "password": "bar"}) == {
        "pass": "********",
        "password": "********",
    }


def test_as_postgres_sql_query_str():
    assert (
        as_postgres_sql_query_str(
            sa.select(users.c.name).where(users.c.id == 1)
        ).replace("\n", "")
        == "SELECT users.name FROM users WHERE users.id = 1"
    )
