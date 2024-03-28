import re
from copy import deepcopy

import sqlalchemy as sa
from sqlalchemy.engine import Engine
from yarl import URL

from .models.base import metadata


def build_url(
    *,
    database: str = "",
    user: str = "",
    password: str = "",
    host: str = "127.0.0.1",
    port: int | str = 5432,
    **_kwargs,
) -> URL:
    """
    Safe build pg url as 'postgresql+psycopg2://{user}:{password}@{host}:{port}/{database}'
    """
    return URL.build(
        scheme="postgresql+psycopg2",
        user=user,
        password=password,
        host=host,
        port=int(port),
        path=f"/{database}",
    )
    # _kwargs allows expand on larger dicts without raising exceptions


def create_tables(dsn: URL):
    engine: Engine | None = None
    try:
        engine = sa.create_engine(str(dsn))
        assert engine  # nosec
        metadata.create_all(engine)
    finally:
        if engine:
            engine.dispose()


def raise_if_not_responsive(dsn: URL, *, verbose=False):
    """Checks whether database is responsive, otherwise it throws exception"""
    engine: Engine | None = None
    try:
        engine = sa.create_engine(
            str(dsn), echo=verbose, echo_pool=verbose, pool_timeout=5
        )
        assert engine  # nosec
        conn = engine.connect()
        conn.close()
    finally:
        if engine:
            engine.dispose()


_URL_PASS_RE = re.compile(r":(\w+)@")


def hide_url_pass(url: str | URL) -> str:
    return _URL_PASS_RE.sub(":********@", str(url))


def hide_dict_pass(data: dict) -> dict:
    data_clone = deepcopy(data)
    for key in data_clone:
        if "pass" in key:
            data_clone[key] = "*" * 8
        elif key == "url":
            data_clone[key] = hide_url_pass(data[key])
    return data_clone
