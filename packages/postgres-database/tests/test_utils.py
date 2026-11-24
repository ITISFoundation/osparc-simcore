# pylint: disable=no-value-for-parameter
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import pytest
import sqlalchemy as sa
from simcore_postgres_database.models.users import users
from simcore_postgres_database.utils import (
    as_async_dsn,
    as_postgres_sql_query_str,
    build_url,
    hide_dict_pass,
    hide_url_pass,
)
from sqlalchemy.ext.asyncio import create_async_engine
from yarl import URL

_SYNC_URL = "postgresql+psycopg://user:pass@127.0.0.1:5432/db"


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
        as_postgres_sql_query_str(sa.select(users.c.name).where(users.c.id == 1)).replace("\n", "")
        == "SELECT users.name FROM users WHERE users.id = 1"
    )


@pytest.mark.parametrize(
    "url",
    [_SYNC_URL, URL(_SYNC_URL), sa.engine.make_url(_SYNC_URL)],
    ids=["str", "yarl", "sqlalchemy"],
)
def test_as_async_dsn(url):
    async_dsn = as_async_dsn(url)
    assert async_dsn == "postgresql+asyncpg://user:pass@127.0.0.1:5432/db"
    assert create_async_engine(async_dsn).dialect.driver == "asyncpg"


def test_build_url_opens_with_the_psycopg_driver():
    url = build_url(
        database="db",
        user="user",
        password="pass",  # noqa: S106
        host="127.0.0.1",
        port=5432,
    )
    assert sa.create_engine(str(url)).dialect.driver == "psycopg"
