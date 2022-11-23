# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import json
from typing import Callable
from uuid import UUID

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient
from faker import Faker
from pydantic import BaseModel, Extra, Field
from servicelib.aiohttp.requests_validation import (
    parse_request_body_as,
    parse_request_path_parameters_as,
    parse_request_query_parameters_as,
)
from servicelib.json_serialization import json_dumps

RQT_USERID_KEY = f"{__name__}.user_id"
APP_SECRET_KEY = f"{__name__}.secret"


def jsonable_encoder(data):
    # Neither models_library nor fastapi is not part of requirements.
    # Q&D replacement for fastapi.encoders.jsonable_encoder
    return json.loads(json_dumps(data))


class MyRequestContext(BaseModel):
    user_id: int = Field(alias=RQT_USERID_KEY)
    secret: str = Field(alias=APP_SECRET_KEY)

    @classmethod
    def create_fake(cls, faker: Faker):
        return cls(user_id=faker.pyint(), secret=faker.password())


class MyRequestPathParams(BaseModel):
    project_uuid: UUID

    class Config:
        extra = Extra.forbid

    @classmethod
    def create_fake(cls, faker: Faker):
        return cls(project_uuid=faker.uuid4())


class MyRequestQueryParams(BaseModel):
    is_ok: bool = True
    label: str

    def as_params(self, **kwargs) -> dict[str, str]:
        data = self.dict(**kwargs)
        return {k: f"{v}" for k, v in data.items()}

    @classmethod
    def create_fake(cls, faker: Faker):
        return cls(is_ok=faker.pybool(), label=faker.word())


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


@pytest.fixture
def client(event_loop, aiohttp_client: Callable, faker: Faker) -> TestClient:
    """
    Some app that:

    - creates app and request context
    - has a handler that parses request params, query and body

    """

    async def _handler(request: web.Request) -> web.Response:
        # --------- UNDER TEST -------
        # NOTE: app context does NOT need to be validated everytime!
        context = MyRequestContext.parse_obj({**dict(request.app), **dict(request)})

        path_params = parse_request_path_parameters_as(
            MyRequestPathParams, request, use_enveloped_error_v1=False
        )
        query_params = parse_request_query_parameters_as(
            MyRequestQueryParams, request, use_enveloped_error_v1=False
        )
        body = await parse_request_body_as(
            MyBody, request, use_enveloped_error_v1=False
        )
        # ---------------------------

        return web.json_response(
            {
                "parameters": path_params.dict(),
                "queries": query_params.dict(),
                "body": body.dict(),
                "context": context.dict(),
            },
            dumps=json_dumps,
        )

    # ---

    @web.middleware
    async def _middleware(request: web.Request, handler):
        # request context
        request[RQT_USERID_KEY] = 42
        request["RQT_IGNORE_CONTEXT"] = "not interesting"
        resp = await handler(request)
        return resp

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

    return event_loop.run_until_complete(aiohttp_client(app))


@pytest.fixture
def path_params(faker: Faker):
    path_params = MyRequestPathParams.create_fake(faker)
    return path_params


@pytest.fixture
def query_params(faker: Faker) -> MyRequestQueryParams:
    return MyRequestQueryParams.create_fake(faker)


@pytest.fixture
def body(faker: Faker) -> MyBody:
    return MyBody.create_fake(faker)


async def test_parse_request_as(
    client: TestClient,
    path_params: MyRequestPathParams,
    query_params: MyRequestQueryParams,
    body: MyBody,
):
    assert client.app
    r = await client.get(
        f"/projects/{path_params.project_uuid}",
        params=query_params.as_params(),
        json=body.dict(),
    )
    assert r.status == web.HTTPOk.status_code, f"{await r.text()}"

    got = await r.json()

    assert got["parameters"] == jsonable_encoder(path_params.dict())
    assert got["queries"] == jsonable_encoder(query_params.dict())
    assert got["body"] == body.dict()
    assert got["context"] == {
        "secret": client.app[APP_SECRET_KEY],
        "user_id": 42,
    }


async def test_parse_request_with_invalid_path_params(
    client: TestClient,
    query_params: MyRequestQueryParams,
    body: MyBody,
):

    r = await client.get(
        "/projects/invalid-uuid",
        params=query_params.as_params(),
        json=body.dict(),
    )
    assert r.status == web.HTTPUnprocessableEntity.status_code, f"{await r.text()}"

    response_body = await r.json()
    assert response_body["error"].pop("resource")
    assert response_body == {
        "error": {
            "msg": "Invalid parameter/s 'project_uuid' in request path",
            "details": [
                {
                    "loc": "project_uuid",
                    "msg": "value is not a valid uuid",
                    "type": "type_error.uuid",
                }
            ],
        }
    }


async def test_parse_request_with_invalid_query_params(
    client: TestClient,
    path_params: MyRequestPathParams,
    body: MyBody,
):

    r = await client.get(
        f"/projects/{path_params.project_uuid}",
        params={},
        json=body.dict(),
    )
    assert r.status == web.HTTPUnprocessableEntity.status_code, f"{await r.text()}"

    response_body = await r.json()
    assert response_body["error"].pop("resource")
    assert response_body == {
        "error": {
            "msg": "Invalid parameter/s 'label' in request query",
            "details": [
                {
                    "loc": "label",
                    "msg": "field required",
                    "type": "value_error.missing",
                }
            ],
        }
    }


async def test_parse_request_with_invalid_body(
    client: TestClient,
    path_params: MyRequestPathParams,
    query_params: MyRequestQueryParams,
):

    r = await client.get(
        f"/projects/{path_params.project_uuid}",
        params=query_params.as_params(),
        json={"invalid": "body"},
    )
    assert r.status == web.HTTPUnprocessableEntity.status_code, f"{await r.text()}"

    response_body = await r.json()

    assert response_body["error"].pop("resource")

    assert response_body == {
        "error": {
            "msg": "Invalid field/s 'x, z' in request body",
            "details": [
                {
                    "loc": "x",
                    "msg": "field required",
                    "type": "value_error.missing",
                },
                {
                    "loc": "z",
                    "msg": "field required",
                    "type": "value_error.missing",
                },
            ],
        }
    }


async def test_parse_request_with_invalid_json_body(
    client: TestClient,
    path_params: MyRequestPathParams,
    query_params: MyRequestQueryParams,
):

    r = await client.get(
        f"/projects/{path_params.project_uuid}",
        params=query_params.as_params(),
        data=b"[ 1 2, 3 'broken-json' ]",
    )

    body = await r.text()
    assert r.status == web.HTTPBadRequest.status_code, body
