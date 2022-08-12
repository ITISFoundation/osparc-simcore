# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import asyncio
from unittest.mock import Mock

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
from pytest_simcore.helpers.utils_assert import assert_status
from simcore_service_webserver.login.settings import LoginOptions, get_plugin_options
from simcore_service_webserver.login.storage import AsyncpgStorage, get_plugin_storage

EMAIL, PASSWORD, PHONE = "tester@test.com", "password", "+12345678912"


@pytest.fixture
def client(
    event_loop: asyncio.AbstractEventLoop,
    aiohttp_client,
    web_server: TestServer,
    mock_orphaned_services,
) -> TestClient:
    cli = event_loop.run_until_complete(aiohttp_client(web_server))
    return cli


@pytest.fixture
def cfg(client: TestClient) -> LoginOptions:
    cfg = get_plugin_options(client.app)
    assert cfg
    return cfg


@pytest.fixture
def db(client: TestClient) -> AsyncpgStorage:
    db: AsyncpgStorage = get_plugin_storage(client.app)
    assert db
    return db


# TESTS ---------------------------------------------------------------------------


@pytest.fixture
def mocked_twilio_service(mocker) -> dict[str, Mock]:
    raise NotImplementedError


async def test_it(
    client: TestClient,
    db: AsyncpgStorage,
    mocked_twilio_service: dict[str, Mock],
):

    # register email+password -----------------------

    # 1. submit
    url = client.app.router["auth_register"].url_for()
    r = await client.post(
        url,
        json={
            "email": EMAIL,
            "password": PASSWORD,
            "confirm": PASSWORD,
        },
    )
    await assert_status(r, web.HTTPOk)
    # TODO: check email was sent
    # TODO: use email link

    # 2. confirmation
    r = await client.get(url)
    await assert_status(r, web.HTTPOk)

    # TODO: check email+password registered

    # register phone -----------------------

    # 1. submit
    url = client.app.router["auth_verify_2fa_phone"].url_for()
    r = await client.post(
        url,
        json={
            "email": EMAIL,
            "phone": PHONE,
        },
    )
    await assert_status(r, web.HTTPOk)

    # TODO: check code generated
    # TODO: check sms sent
    assert mocked_twilio_service["register"].called

    # TODO: get code sent by SMS
    received_code = 1234

    # 2. confirmation
    url = client.app.router["auth_validate_2fa_register"].url_for()
    r = await client.post(
        url,
        json={
            "email": EMAIL,
            "phone": PHONE,
            "code": received_code,
        },
    )
    await assert_status(r, web.HTTPOk)
    # TODO: check user has phone confirmed

    # login -----------------------

    # 1. check email/password then send SMS
    url = client.app.router["auth_login"].url_for()
    r = await client.post(
        url,
        json={
            "email": EMAIL,
            "password": PASSWORD,
            "confirm": PASSWORD,
        },
    )
    await assert_status(r, web.HTTPAccepted)

    # 2. check SMS code
    url = client.app.router["auth_validate_2fa_login"].url_for()
    r = await client.post(
        url,
        json={
            "email": EMAIL,
            "code": received_code,
        },
    )
    await assert_status(r, web.HTTPOk)
