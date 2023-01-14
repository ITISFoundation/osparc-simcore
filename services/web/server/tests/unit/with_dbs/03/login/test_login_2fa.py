# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import asyncio
from unittest.mock import Mock

import pytest
import sqlalchemy as sa
from aiohttp import web
from aiohttp.test_utils import TestClient, make_mocked_request
from faker import Faker
from pytest import CaptureFixture, MonkeyPatch
from pytest_simcore.helpers import utils_login
from pytest_simcore.helpers.utils_assert import assert_status
from pytest_simcore.helpers.utils_envs import EnvVarsDict, setenvs_from_dict
from pytest_simcore.helpers.utils_login import parse_link, parse_test_marks
from simcore_postgres_database.models.products import products
from simcore_service_webserver.db_models import UserStatus
from simcore_service_webserver.login._2fa import (
    _do_create_2fa_code,
    _generage_2fa_code,
    create_2fa_code,
    delete_2fa_code,
    get_2fa_code,
    get_redis_validation_code_client,
    send_email_code,
)
from simcore_service_webserver.login.storage import AsyncpgStorage


@pytest.fixture
def app_environment(app_environment: EnvVarsDict, monkeypatch: MonkeyPatch):
    setenvs_from_dict(
        monkeypatch,
        {
            "LOGIN_REGISTRATION_CONFIRMATION_REQUIRED": "1",
            "LOGIN_REGISTRATION_INVITATION_REQUIRED": "0",
            "LOGIN_2FA_CODE_EXPIRATION_SEC": "60",
        },
    )


@pytest.fixture
def postgres_db(postgres_db: sa.engine.Engine):
    # adds fake twilio_messaging_sid in osparc product (pre-initialized)
    stmt = (
        products.update()
        .values(
            twilio_messaging_sid="x" * 34,
            login_settings={"two_factor_enabled": True},  # <--- 2FA Enabled
        )
        .where(products.c.name == "osparc")
    )
    postgres_db.execute(stmt)
    return postgres_db


@pytest.fixture
def mocked_twilio_service(mocker) -> dict[str, Mock]:
    return {
        "send_sms_code_for_registration": mocker.patch(
            "simcore_service_webserver.login.handlers_registration.send_sms_code",
            autospec=True,
        ),
        "send_sms_code_for_login": mocker.patch(
            "simcore_service_webserver.login.handlers_auth.send_sms_code",
            autospec=True,
        ),
    }


async def test_2fa_code_operations(client: TestClient):
    assert client.app

    # get/delete an entry that does not exist
    assert await get_2fa_code(client.app, "invalid@bar.com") is None
    await delete_2fa_code(client.app, "invalid@bar.com")

    # set/get/delete
    email = "foo@bar.com"
    code = await create_2fa_code(client.app, user_email=email, expiration_in_seconds=60)

    assert await get_2fa_code(client.app, email) == code
    await delete_2fa_code(client.app, email)

    # expired
    email = "expired@bar.com"
    code = await _do_create_2fa_code(
        get_redis_validation_code_client(client.app), email, expiration_seconds=1
    )
    await asyncio.sleep(1.5)
    assert await get_2fa_code(client.app, email) is None


@pytest.mark.acceptance_test
async def test_workflow_register_and_login_with_2fa(
    client: TestClient,
    db: AsyncpgStorage,
    capsys: CaptureFixture,
    fake_user_email: str,
    fake_user_password: str,
    fake_user_phone_number: str,
    mocked_twilio_service: dict[str, Mock],
):
    assert client.app

    # register email+password -----------------------

    # 1. submit
    url = client.app.router["auth_register"].url_for()
    response = await client.post(
        f"{url}",
        json={
            "email": fake_user_email,
            "password": fake_user_password,
            "confirm": fake_user_password,
        },
    )
    await assert_status(response, web.HTTPOk)

    # check email was sent
    def _get_confirmation_link_from_email():
        out, _ = capsys.readouterr()
        link = parse_link(out)
        assert "/auth/confirmation/" in str(link)
        return link

    url = _get_confirmation_link_from_email()

    # 2. confirmation
    response = await client.get(url)
    assert response.status == web.HTTPOk.status_code

    # check email+password registered
    user = await db.get_user({"email": fake_user_email})
    assert user["status"] == UserStatus.ACTIVE.name
    assert user["phone"] is None

    # register phone --------------------------------------------------

    # 1. submit
    url = client.app.router["auth_register_phone"].url_for()
    response = await client.post(
        f"{url}",
        json={
            "email": fake_user_email,
            "phone": fake_user_phone_number,
        },
    )
    await assert_status(response, web.HTTPAccepted)

    # check code generated and SMS sent
    assert mocked_twilio_service["send_sms_code_for_registration"].called
    kwargs = mocked_twilio_service["send_sms_code_for_registration"].call_args.kwargs
    phone, received_code = kwargs["phone_number"], kwargs["code"]
    assert phone == fake_user_phone_number

    # check phone still NOT in db (TODO: should be in database and unconfirmed)
    user = await db.get_user({"email": fake_user_email})
    assert user["status"] == UserStatus.ACTIVE.name
    assert user["phone"] is None

    # 2. confirmation
    url = client.app.router["auth_phone_confirmation"].url_for()
    response = await client.post(
        f"{url}",
        json={
            "email": fake_user_email,
            "phone": fake_user_phone_number,
            "code": received_code,
        },
    )
    await assert_status(response, web.HTTPOk)
    # check user has phone confirmed
    user = await db.get_user({"email": fake_user_email})
    assert user["status"] == UserStatus.ACTIVE.name
    assert user["phone"] == fake_user_phone_number

    # login ---------------------------------------------------------

    # 1. check email/password then send SMS
    url = client.app.router["auth_login"].url_for()
    response = await client.post(
        f"{url}",
        json={
            "email": fake_user_email,
            "password": fake_user_password,
        },
    )
    data, _ = await assert_status(response, web.HTTPAccepted)

    assert data["code"] == "SMS_CODE_REQUIRED"

    # assert SMS was sent
    kwargs = mocked_twilio_service["send_sms_code_for_login"].call_args.kwargs
    phone, received_code = kwargs["phone_number"], kwargs["code"]
    assert phone == fake_user_phone_number

    # 2. check SMS code
    url = client.app.router["auth_login_2fa"].url_for()
    response = await client.post(
        f"{url}",
        json={
            "email": fake_user_email,
            "code": received_code,
        },
    )
    # WARNING: while debugging, breakpoints can add too much delay
    # and make 2fa TTL expire resulting in this validation fail
    await assert_status(response, web.HTTPOk)

    # assert users is successfully registered
    user = await db.get_user({"email": fake_user_email})
    assert user["email"] == fake_user_email
    assert user["phone"] == fake_user_phone_number
    assert user["status"] == UserStatus.ACTIVE.value


async def test_register_phone_fails_with_used_number(
    client: TestClient,
    db: AsyncpgStorage,
    fake_user_email: str,
    fake_user_password: str,
    fake_user_phone_number: str,
):
    """
    Tests https://github.com/ITISFoundation/osparc-simcore/issues/3304
    """
    assert client.app

    # some user ALREADY registered with the same phone
    await utils_login.create_fake_user(db, data={"phone": fake_user_phone_number})

    # some registered user w/o phone
    await utils_login.create_fake_user(
        db,
        data={"email": fake_user_email, "password": fake_user_password, "phone": None},
    )

    # 1. login
    url = client.app.router["auth_login"].url_for()
    response = await client.post(
        f"{url}",
        json={
            "email": fake_user_email,
            "password": fake_user_password,
        },
    )
    await assert_status(response, web.HTTPAccepted)

    # 2. register existing phone
    url = client.app.router["auth_register_phone"].url_for()
    response = await client.post(
        f"{url}",
        json={
            "email": fake_user_email,
            "phone": fake_user_phone_number,
        },
    )
    _, error = await assert_status(response, web.HTTPUnauthorized)
    assert "phone" in error["message"]


async def test_send_email_code(
    client: TestClient, faker: Faker, capsys: CaptureFixture
):
    request = make_mocked_request("GET", "/dummy", app=client.app)

    user_email = faker.email()
    support_email = faker.email()
    code = _generage_2fa_code()
    user_name = faker.user_name()

    await send_email_code(
        request,
        user_email=user_email,
        support_email=support_email,
        code=code,
        user_name=user_name,
    )

    out, _ = capsys.readouterr()
    parsed_context = parse_test_marks(out)
    assert parsed_context["code"] == f"{code}"
    assert parsed_context["name"] == user_name.capitalize()
    assert parsed_context["support_email"] == support_email
