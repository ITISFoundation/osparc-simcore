# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from datetime import datetime
from typing import Callable

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient
from pydantic import BaseModel, Field, conint
from servicelib.aiohttp.rest_long_running_operations import Operation


@pytest.fixture
def client(event_loop, aiohttp_client: Callable) -> TestClient:

    # models
    class LongRunningWriteBookMeta(BaseModel):
        progress: conint(ge=0, le=100) = Field(default=0)  # type: ignore
        created: datetime = Field(default_factory=datetime.now)

    class BookGet(BaseModel):
        title: str
        author: str
        text: str

    class Error(BaseModel):
        details: str

    # service

    # routes
    routes = web.RouteTableDef()

    # long running operations API (standard)
    @routes.get("/v1/operations")
    async def list_operations(request: web.Request) -> web.Response:
        ...

    @routes.get("/v1/operations/{name}", name="get_operation")
    async def get_operation(request: web.Request) -> web.Response:
        ...

    # book API (example)
    WriteBookLongRunningOp = Operation[LongRunningWriteBookMeta, BookGet, Error]

    @routes.post("/v1/publishers/{publisher_id}/books:write")
    async def write_a_book(request: web.Request) -> web.Response:
        publisher_id = request.match_info["publisher_id"]
        body = await request.json()

        # identify this write_a_book operation
        operation_hash = f"{request.rel_url}"

        # if operation_hash is already running ???
        # otherwise

        # spawn a task to write a book
        # register wit

        rel_url = (
            request.app.router["get_operation"].url_for(name=operation_hash).relative()
        )

        op = WriteBookLongRunningOp(
            name=f"{rel_url}", metadata=LongRunningWriteBookMeta()
        )
        return web.json_response(text=op.json())

    # init
    app = web.Application()
    app.add_routes(routes)
    return event_loop.run_until_complete(aiohttp_client(app))
