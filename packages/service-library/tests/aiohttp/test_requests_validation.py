# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from typing import Any
from uuid import UUID

import pytest
from aiohttp import web
from aiohttp.test_utils import make_mocked_request
from faker import Faker
from jsonschema import ValidationError
from pydantic import BaseModel, Field
from servicelib.aiohttp.requests_validation import (
    parse_request_body_as,
    parse_request_context_as,
    parse_request_parameters_as,
)
from yarl import URL

# HELPERS
RQT_USERID_KEY = f"{__name__}.user_id"
APP_SECRET_KEY = f"{__name__}.secret"


class MyRequestContext(BaseModel):
    user_id: int = Field(alias=RQT_USERID_KEY)
    secret: str = Field(alias=APP_SECRET_KEY)

    @classmethod
    def create_fake(cls, faker: Faker):
        return cls(user_id=faker.pyint(), secret=faker.password())


class MyRequestParameters(BaseModel):
    project_uuid: UUID
    is_ok: bool = True

    @classmethod
    def create_fake(cls, faker: Faker):
        return cls(project_uuid=faker.uuid4(), is_ok=faker.pybool())


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


def create_fake_request(
    app: web.Application, params: dict[str, str], queries: dict[str, Any], body: Any
):
    url = URL.build(path="/projects/{project_uuid}/".format(**params), query=queries)

    request = make_mocked_request(
        "GET",
        f"{url}",
        match_info=params,
        app=app,
        payload=body,
    )
    return request


# TESTS


async def test_parse_request_as(
    app: web.Application,
    faker: Faker,
):

    context = MyRequestContext.create_fake(faker)
    params = MyRequestParameters.create_fake(faker)
    body = MyBody.create_fake(faker)

    app = web.Application()
    app[APP_SECRET_KEY] = context.secret
    app["SKIP_THIS"] = 0

    request = create_fake_request(
        app,
        params=params.dict(include={"project_uuid"}),
        queries=params.dict(exclude={"project_uuid"}),
        body=body.json(),
    )
    request[RQT_USERID_KEY] = context.user_id
    request["SKIP_ALSO_THIS"] = 0

    # params
    valid_params = parse_request_parameters_as(MyRequestParameters, request)
    assert valid_params == params

    # body
    valid_body = await parse_request_body_as(MyBody, request)
    assert valid_body == body

    # context
    valid_context = parse_request_context_as(MyRequestContext, request)
    assert valid_context == context


async def test_parse_request_as_raises_http_error(
    app: web.Application,
    faker: Faker,
):

    body = MyBody.create_fake(faker)

    request = create_fake_request(
        app,
        params={"project_uuid": "invalid-uuid"},
        queries={},
        body={"wrong": 33},
    )

    # params
    with pytest.raises(web.HTTPBadRequest) as exc_info:
        parse_request_parameters_as(MyRequestParameters, request)

    bad_request_exc = exc_info.value
    assert "project_uuid" in bad_request_exc.reason

    # body
    with pytest.raises(web.HTTPBadRequest) as exc_info:
        await parse_request_body_as(MyBody, request)

    bad_request_exc = exc_info.value
    assert "wrong" in bad_request_exc.reason

    # context
    with pytest.raises(ValidationError):
        parse_request_context_as(MyRequestContext, request)
