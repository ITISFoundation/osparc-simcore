# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from uuid import UUID

import pytest
from aiohttp import web
from aiohttp.test_utils import make_mocked_request
from faker import Faker
from pydantic import BaseModel, ValidationError
from servicelib.aiohttp.requests_utils import parse_request_parameters_as


class MyRequestParameters(BaseModel):
    user_id: int  # app[]
    project_uuid: UUID
    is_ok: bool = True


RQT_USERID_KEY = f"{__name__}.user_id"
APP_KEYS_MAP = {"user_id": RQT_USERID_KEY}


@pytest.fixture
def fake_params(faker: Faker):
    return MyRequestParameters(
        user_id=faker.pyint(), project_uuid=faker.uuid4(), is_ok=faker.pybool()
    )


@pytest.fixture
def app(fake_params: MyRequestParameters) -> web.Application:
    app = web.Application()
    app[RQT_USERID_KEY] = fake_params.user_id
    return app


# TESTS


def test_parse_request_parameters_as(
    fake_params: MyRequestParameters, app: web.Application
):

    request = make_mocked_request(
        "GET",
        f"/projects/{fake_params.project_uuid}?is_ok={fake_params.is_ok}",
        match_info={"project_uuid": fake_params.project_uuid},
        app=app,
    )

    parsed_params = parse_request_parameters_as(
        MyRequestParameters, request, app_storage_map=APP_KEYS_MAP
    )

    assert parsed_params == fake_params


def test_parse_request_parameters_raises_http_error(
    fake_params: MyRequestParameters, app: web.Application
):

    request = make_mocked_request(
        "GET",
        f"/projects/1234?is_ok={fake_params.is_ok}",
        match_info={"project_uuid": "1234"},
        app=app,
    )

    with pytest.raises(web.HTTPBadRequest) as exc_info:
        parse_request_parameters_as(
            MyRequestParameters, request, app_storage_map=APP_KEYS_MAP
        )
    bad_request_exc = exc_info.value
    assert "project_uuid" in bad_request_exc.reason


def test_parse_request_parameters_raises_validation_error(
    fake_params: MyRequestParameters,
):

    request = make_mocked_request(
        "GET",
        f"/projects/{fake_params.project_uuid}?is_ok={fake_params.is_ok}",
        match_info={"project_uuid": fake_params.project_uuid},
        app=web.Application(),  # no user!
    )

    with pytest.raises(ValidationError) as exc_info:
        parse_request_parameters_as(
            MyRequestParameters, request, app_storage_map=APP_KEYS_MAP
        )

    assert "user_id" in exc_info.value.errors()[0]["loc"]
