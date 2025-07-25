# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import json
from collections.abc import Callable
from uuid import UUID

import pytest
import pytest_asyncio
from aiohttp import web
from aiohttp.test_utils import TestClient, make_mocked_request
from common_library.json_serialization import json_dumps
from faker import Faker
from models_library.rest_base import RequestParameters, StrictRequestParameters
from models_library.rest_error import EnvelopedError
from models_library.rest_ordering import (
    OrderBy,
    OrderDirection,
    create_ordering_query_model_class,
)
from pydantic import BaseModel, ConfigDict, Field
from servicelib.aiohttp import status
from servicelib.aiohttp.requests_validation import (
    parse_request_body_as,
    parse_request_headers_as,
    parse_request_path_parameters_as,
    parse_request_query_parameters_as,
)
from yarl import URL

RQT_USERID_KEY = f"{__name__}.user_id"
APP_SECRET_KEY = f"{__name__}.secret"


def jsonable_encoder(data):
    # Neither models_library nor fastapi is not part of requirements.
    # Q&D replacement for fastapi.encoders.jsonable_encoder
    return json.loads(json_dumps(data))


class MyRequestContext(RequestParameters):
    user_id: int = Field(alias=RQT_USERID_KEY)
    secret: str = Field(alias=APP_SECRET_KEY)

    @classmethod
    def create_fake(cls, faker: Faker):
        return cls(user_id=faker.pyint(), secret=faker.password())


class MyRequestPathParams(StrictRequestParameters):
    project_uuid: UUID

    @classmethod
    def create_fake(cls, faker: Faker):
        return cls(project_uuid=faker.uuid4())


class MyRequestQueryParams(RequestParameters):
    is_ok: bool = True
    label: str

    @classmethod
    def create_fake(cls, faker: Faker):
        return cls(is_ok=faker.pybool(), label=faker.word())


class MyRequestHeadersParams(RequestParameters):
    user_agent: str = Field(alias="X-Simcore-User-Agent")
    optional_header: str | None = Field(default=None, alias="X-Simcore-Optional-Header")
    model_config = ConfigDict(
        populate_by_name=False,
    )

    @classmethod
    def create_fake(cls, faker: Faker):
        return cls(
            **{
                "X-Simcore-User-Agent": faker.pystr(),
                "X-Simcore-Optional-Header": faker.word(),
            }
        )


class Sub(BaseModel):
    a: float = 33

    @classmethod
    def create_fake(cls, faker: Faker):
        return cls(a=faker.pyfloat())


class MyBody(BaseModel):
    x: int
    y: bool = False
    z: Sub

    @classmethod
    def create_fake(cls, faker: Faker):
        return cls(x=faker.pyint(), y=faker.pybool(), z=Sub.create_fake(faker))


@pytest_asyncio.fixture(loop_scope="function", scope="function")
async def client(aiohttp_client: Callable, faker: Faker) -> TestClient:
    """
    Some app that:

    - creates app and request context
    - has a handler that parses request params, query and body

    """

    async def _handler(request: web.Request) -> web.Response:
        # --------- UNDER TEST -------
        # NOTE: app context does NOT need to be validated everytime!
        context = MyRequestContext.model_validate(
            {**dict(request.app), **dict(request)}
        )

        path_params = parse_request_path_parameters_as(MyRequestPathParams, request)
        query_params = parse_request_query_parameters_as(MyRequestQueryParams, request)
        headers_params = parse_request_headers_as(MyRequestHeadersParams, request)
        body = await parse_request_body_as(MyBody, request)
        # ---------------------------

        return web.json_response(
            {
                "parameters": path_params.model_dump(),
                "queries": query_params.model_dump(),
                "body": body.model_dump(),
                "context": context.model_dump(),
                "headers": headers_params.model_dump(),
            },
            dumps=json_dumps,
        )

    # ---

    @web.middleware
    async def _middleware(request: web.Request, handler):
        # request context
        request[RQT_USERID_KEY] = 42
        request["RQT_IGNORE_CONTEXT"] = "not interesting"
        return await handler(request)

    app = web.Application(
        middlewares=[
            _middleware,
        ]
    )

    # app context
    app[APP_SECRET_KEY] = faker.password()
    app["APP_IGNORE_CONTEXT"] = "not interesting"

    # adds handler
    app.add_routes([web.get("/projects/{project_uuid}", _handler)])

    return await aiohttp_client(app)


@pytest.fixture
def path_params(faker: Faker) -> MyRequestPathParams:
    return MyRequestPathParams.create_fake(faker)


@pytest.fixture
def query_params(faker: Faker) -> MyRequestQueryParams:
    return MyRequestQueryParams.create_fake(faker)


@pytest.fixture
def body(faker: Faker) -> MyBody:
    return MyBody.create_fake(faker)


@pytest.fixture
def headers_params(faker: Faker) -> MyRequestHeadersParams:
    return MyRequestHeadersParams.create_fake(faker)


async def test_parse_request_as(
    client: TestClient,
    path_params: MyRequestPathParams,
    query_params: MyRequestQueryParams,
    body: MyBody,
    headers_params: MyRequestHeadersParams,
):
    assert client.app
    r = await client.get(
        f"/projects/{path_params.project_uuid}",
        params=query_params.as_params(),
        json=body.model_dump(),
        headers=headers_params.model_dump(by_alias=True),
    )
    assert r.status == status.HTTP_200_OK, f"{await r.text()}"

    got = await r.json()

    assert got["parameters"] == jsonable_encoder(path_params.model_dump())
    assert got["queries"] == jsonable_encoder(query_params.model_dump())
    assert got["body"] == body.model_dump()
    assert got["context"] == {
        "secret": client.app[APP_SECRET_KEY],
        "user_id": 42,
    }
    assert got["headers"] == jsonable_encoder(headers_params.model_dump())


async def test_parse_request_with_invalid_path_params(
    client: TestClient,
    query_params: MyRequestQueryParams,
    body: MyBody,
    headers_params: MyRequestHeadersParams,
):

    r = await client.get(
        "/projects/invalid-uuid",
        params=query_params.as_params(),
        json=body.model_dump(),
        headers=headers_params.model_dump(by_alias=True),
    )
    assert r.status == status.HTTP_422_UNPROCESSABLE_ENTITY, f"{await r.text()}"

    response_body = await r.json()

    error_model = EnvelopedError.model_validate(response_body).error
    assert error_model.message == "Invalid parameter/s 'project_uuid' in request path"
    assert error_model.status == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert error_model.errors[0].field == "project_uuid"
    assert error_model.errors[0].code == "uuid_parsing"


async def test_parse_request_with_invalid_query_params(
    client: TestClient,
    path_params: MyRequestPathParams,
    body: MyBody,
    headers_params: MyRequestHeadersParams,
):

    r = await client.get(
        f"/projects/{path_params.project_uuid}",
        params={},
        json=body.model_dump(),
        headers=headers_params.model_dump(by_alias=True),
    )
    assert r.status == status.HTTP_422_UNPROCESSABLE_ENTITY, f"{await r.text()}"

    response_body = await r.json()
    error_model = EnvelopedError.model_validate(response_body).error
    assert error_model.message == "Invalid parameter/s 'label' in request query"
    assert error_model.status == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert error_model.errors[0].field == "label"
    assert error_model.errors[0].code == "missing"


async def test_parse_request_with_invalid_body(
    client: TestClient,
    path_params: MyRequestPathParams,
    query_params: MyRequestQueryParams,
    headers_params: MyRequestHeadersParams,
):

    r = await client.get(
        f"/projects/{path_params.project_uuid}",
        params=query_params.as_params(),
        json={"invalid": "body"},
        headers=headers_params.model_dump(by_alias=True),
    )
    assert r.status == status.HTTP_422_UNPROCESSABLE_ENTITY, f"{await r.text()}"

    response_body = await r.json()

    error_model = EnvelopedError.model_validate(response_body).error
    assert error_model.message == "Invalid field/s 'x, z' in request body"
    assert error_model.status == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert error_model.errors[0].field == "x"
    assert error_model.errors[0].code == "missing"


async def test_parse_request_with_invalid_json_body(
    client: TestClient,
    path_params: MyRequestPathParams,
    query_params: MyRequestQueryParams,
    headers_params: MyRequestHeadersParams,
):

    r = await client.get(
        f"/projects/{path_params.project_uuid}",
        params=query_params.as_params(),
        data=b"[ 1 2, 3 'broken-json' ]",
        headers=headers_params.model_dump(by_alias=True),
    )

    body = await r.text()
    assert r.status == status.HTTP_400_BAD_REQUEST, body


async def test_parse_request_with_invalid_headers_params(
    client: TestClient,
    path_params: MyRequestPathParams,
    query_params: MyRequestQueryParams,
    body: MyBody,
    headers_params: MyRequestHeadersParams,
):

    r = await client.get(
        f"/projects/{path_params.project_uuid}",
        params=query_params.as_params(),
        json=body.model_dump(),
        headers=headers_params.model_dump(),  # we pass the wrong names
    )
    assert r.status == status.HTTP_422_UNPROCESSABLE_ENTITY, f"{await r.text()}"

    response_body = await r.json()

    error_model = EnvelopedError.model_validate(response_body).error
    assert (
        error_model.message
        == "Invalid parameter/s 'X-Simcore-User-Agent' in request headers"
    )
    assert error_model.status == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert error_model.errors[0].field == "X-Simcore-User-Agent"
    assert error_model.errors[0].code == "missing"


def test_parse_request_query_parameters_as_with_order_by_query_models():

    OrderQueryModel = create_ordering_query_model_class(
        ordering_fields={"modified", "name"}, default=OrderBy(field="name")
    )

    expected = OrderBy(field="name", direction=OrderDirection.ASC)

    url = URL("/test").with_query(order_by=expected.model_dump_json())

    request = make_mocked_request("GET", path=f"{url}")

    query_params = parse_request_query_parameters_as(OrderQueryModel, request)

    assert OrderBy.model_construct(**query_params.order_by.model_dump()) == expected
