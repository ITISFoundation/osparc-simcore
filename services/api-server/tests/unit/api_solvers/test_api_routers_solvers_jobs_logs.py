# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import asyncio
import datetime
import json
from collections.abc import AsyncIterable

import httpx
import pytest
from fastapi import FastAPI
from fastapi.responses import StreamingResponse

# - docker OAS: Container logs https://docs.docker.com/engine/api/v1.43/#tag/Container/operation/ContainerLogs
# - Streaming with FastAPI: https://python.plainenglish.io/streaming-with-fastapi-4b86f33bfca
# - Server Side Events (SSE) https://amittallapragada.github.io/docker/fastapi/python/2020/12/23/server-side-events.html
# - Streaming with FastAPI https://python.plainenglish.io/streaming-with-fastapi-4b86f33bfca


_NEW_LINE = "\n"
CHUNK_MSG = "expected" + _NEW_LINE


@pytest.fixture()
def app() -> FastAPI:
    app = FastAPI()

    async def _text_generator() -> AsyncIterable[str]:
        for _ in range(10):
            yield CHUNK_MSG
            await asyncio.sleep(0)

    async def _json_generator() -> AsyncIterable[str]:
        i = 0
        async for text in _text_generator():
            yield json.dumps({"envent_id": i, "data": text}, indent=None) + _NEW_LINE
            i += 1

    @app.get("/logs")
    async def stream_logs(as_json: bool = False):
        if as_json:
            return StreamingResponse(
                _json_generator(), media_type="application/x-ndjson"
            )
        return StreamingResponse(_text_generator())

    return app


@pytest.mark.parametrize("as_json", [True, False])
async def test_it(client: httpx.AsyncClient, as_json: bool):
    # https://www.python-httpx.org/quickstart/#streaming-responses

    chunk_size = len(CHUNK_MSG)

    received = []
    async with client.stream("GET", "/logs") as r:
        async for text in r.aiter_text(chunk_size):
            received.append(text)

    assert (
        received
        == [
            CHUNK_MSG,
        ]
        * 10
    )

    async with client.stream("GET", f"/logs?as_json={1 if as_json else 0}") as r:
        async for line in r.aiter_lines():
            if as_json:
                data = json.loads(line)
                txt = json.dumps(data, indent=1)
            else:
                txt = line

            print(f"{datetime.datetime.now(tz=datetime.timezone.utc)}", txt, flush=True)
