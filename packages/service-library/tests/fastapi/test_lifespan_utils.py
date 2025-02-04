from collections.abc import AsyncIterator

import asgi_lifespan
import pytest
from fastapi import FastAPI
from fastapi_lifespan_manager import State
from servicelib.fastapi.lifespan_utils import combine_lifespans


async def test_multiple_lifespan_managers(capsys: pytest.CaptureFixture):
    async def database_lifespan(app: FastAPI) -> AsyncIterator[State]:
        _ = app
        print("setup DB")
        yield State()
        print("shutdown  DB")

    async def cache_lifespan(app: FastAPI) -> AsyncIterator[State]:
        _ = app
        print("setup CACHE")
        yield State()
        print("shutdown CACHE")

    app = FastAPI(lifespan=combine_lifespans(database_lifespan, cache_lifespan))

    capsys.readouterr()

    async with asgi_lifespan.LifespanManager(app):
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
