# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from unittest.mock import Mock

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient
from pytest import MonkeyPatch
from pytest_simcore.helpers.utils_assert import assert_status
from pytest_simcore.helpers.utils_dict import ConfigDict
from pytest_simcore.helpers.utils_login import parse_link
from simcore_service_webserver.db_models import UserStatus
from simcore_service_webserver.login.settings import LoginOptions, get_plugin_options
from simcore_service_webserver.login.storage import AsyncpgStorage, get_plugin_storage

EMAIL, PASSWORD, PHONE = "tester@test.com", "password", "+12345678912"


@pytest.fixture
def app_cfg(
    app_cfg: ConfigDict,
    env_devel_dict: dict[str, str],
    monkeypatch: MonkeyPatch,
) -> ConfigDict:
    # overrides app_cfg.
    # SEE sections in services/web/server/tests/data/default_app_config-unit.yaml

    # disables GC
    app_cfg["garbage_collector"]["enabled"] = False

    # enables login
    app_cfg["login"] = {
        "enabled": True,
        "registration_confirmation_required": True,
        "registration_invitation_required": False,
    }

    # enable 2FA (via environs)
    monkeypatch.setenv("LOGIN_2FA_REQUIRED", "true")
    for key, value in env_devel_dict.items():
        if key.startswith("TWILIO_"):
            monkeypatch.setenv(key, value)

    return app_cfg


@pytest.fixture
def cfg(client: TestClient) -> LoginOptions:
    assert client.app
    cfg = get_plugin_options(client.app)
    assert cfg
    return cfg


@pytest.fixture
def db(client: TestClient) -> AsyncpgStorage:
    assert client.app
    db: AsyncpgStorage = get_plugin_storage(client.app)
    assert db
    return db


@pytest.fixture
def mocked_twilio_service(mocker) -> dict[str, Mock]:
    return {
        "send_sms_code": mocker.patch(
            "simcore_service_webserver.login.handlers.send_sms_code", autospec=True
        )
    }


# TESTS ---------------------------------------------------------------------------


@pytest.mark.acceptance_test
async def test_workflow_register_and_login_with_2fa(
    client: TestClient,
    db: AsyncpgStorage,
    capsys,
    mocked_twilio_service: dict[str, Mock],
):
    assert client.app

    # register email+password -----------------------

    # 1. submit
    url = client.app.router["auth_register"].url_for()
    rsp = await client.post(
        url,
        json={
            "email": EMAIL,
            "password": PASSWORD,
            "confirm": PASSWORD,
        },
    )
    await assert_status(rsp, web.HTTPOk)

    # check email was sent
    def _get_confirmation_link_from_email():
        out, _ = capsys.readouterr()
        link = parse_link(out)
        assert "/auth/confirmation/" in str(link)
        return link

    url = _get_confirmation_link_from_email()

    # 2. confirmation
    rsp = await client.get(url)
    assert rsp.status == web.HTTPOk.status_code

    # check email+password registered
    user = await db.get_user({"email": EMAIL})
    assert user["status"] == UserStatus.ACTIVE.name
    assert user["phone"] is None

    # register phone --------------------------------------------------

    # 1. submit
    url = client.app.router["auth_verify_2fa_phone"].url_for()
    rsp = await client.post(
        url,
        json={
            "email": EMAIL,
            "phone": PHONE,
        },
    )
    await assert_status(rsp, web.HTTPAccepted)

    # check code generated and SMS sent
    assert mocked_twilio_service["send_sms_code"].called
    phone, received_code, _ = mocked_twilio_service["send_sms_code"].call_args.args
    assert phone == PHONE

    # check phone still NOT in db (TODO: should be in database and unconfirmed)
    user = await db.get_user({"email": EMAIL})
    assert user["status"] == UserStatus.ACTIVE.name
    assert user["phone"] is None

    # 2. confirmation
    url = client.app.router["auth_validate_2fa_register"].url_for()
    rsp = await client.post(
        url,
        json={
            "email": EMAIL,
            "phone": PHONE,
            "code": received_code,
        },
    )
    await assert_status(rsp, web.HTTPOk)
    # check user has phone confirmed
    user = await db.get_user({"email": EMAIL})
    assert user["status"] == UserStatus.ACTIVE.name
    assert user["phone"] == PHONE

    # login ---------------------------------------------------------

    # 1. check email/password then send SMS
    url = client.app.router["auth_login"].url_for()
    rsp = await client.post(
        url,
        json={
            "email": EMAIL,
            "password": PASSWORD,
            "confirm": PASSWORD,
        },
    )
    data, _ = await assert_status(rsp, web.HTTPAccepted)

    assert data["code"] == "SMS_CODE_REQUIRED"

    # assert SMS was sent
    phone, received_code, _ = mocked_twilio_service["send_sms_code"].call_args.args
    assert phone == PHONE

    # 2. check SMS code
    url = client.app.router["auth_validate_2fa_login"].url_for()
    rsp = await client.post(
        url,
        json={
            "email": EMAIL,
            "code": received_code,
        },
    )
    await assert_status(rsp, web.HTTPOk)

    # assert users is successfully registered
    user = await db.get_user({"email": EMAIL})
    assert user["email"] == EMAIL
    assert user["phone"] == PHONE
    assert user["status"] == UserStatus.ACTIVE.value
