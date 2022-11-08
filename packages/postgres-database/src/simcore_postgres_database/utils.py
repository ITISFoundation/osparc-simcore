import re
from copy import deepcopy
from typing import Optional, Union

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
    port: int = 5432,
    **_kwargs,
) -> URL:
    """
    Safe build pg url as 'postgresql+psycopg2://{user}:{password}@{host}:{port}/{database}'
    """
    dsn = URL.build(
        scheme="postgresql+psycopg2",
        user=user,
        password=password,
        host=host,
        port=port,
        path=f"/{database}",
    )
    # _kwargs allows expand on larger dicts without raising exceptions
    return dsn


def create_tables(dsn: URL):
    engine: Optional[Engine] = None
    try:
        engine = sa.create_engine(str(dsn))
        assert engine  # nosec
        metadata.create_all(engine)
    finally:
        if engine:
            engine.dispose()


def raise_if_not_responsive(dsn: URL, *, verbose=False):
    """Checks whether database is responsive, otherwise it throws exception"""
    engine: Optional[Engine] = None
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


def hide_url_pass(url: Union[str, URL]) -> str:
    return _URL_PASS_RE.sub(":********@", str(url))


def hide_dict_pass(data: dict) -> dict:
    data_clone = deepcopy(data)
    for key in data_clone:
        if "pass" in key:
            data_clone[key] = "*" * 8
        elif "url" == key:
            data_clone[key] = hide_url_pass(data[key])
    return data_clone
