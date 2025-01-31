from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytest
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from servicelib.fastapi.lifespan_utils import combine_lifespans


async def test_multiple_lifespan_managers(capsys: pytest.CaptureFixture):
    @asynccontextmanager
    async def database_lifespan(_: FastAPI) -> AsyncIterator[None]:
        print("setup DB")
        yield
        print("shutdown  DB")

    @asynccontextmanager
    async def cache_lifespan(_: FastAPI) -> AsyncIterator[None]:
        print("setup CACHE")
        yield
        print("shutdown CACHE")

    app = FastAPI(lifespan=combine_lifespans(database_lifespan, cache_lifespan))

    capsys.readouterr()

    async with LifespanManager(app):
        messages = capsys.readouterr().out

        assert "setup DB" in messages
        assert "setup CACHE" in messages
        assert "shutdown  DB" not in messages
        assert "shutdown CACHE" not in messages

    messages = capsys.readouterr().out

    assert "setup DB" not in messages
    assert "setup CACHE" not in messages
    assert "shutdown  DB" in messages
    assert "shutdown CACHE" in messages
