# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import pytest
import sqlalchemy as sa
from aiohttp.test_utils import TestClient
from pytest_mock import MockFixture
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.monkeypatch_envs import EnvVarsDict, setenvs_from_dict
from pytest_simcore.helpers.webserver_login import UserInfoDict
from servicelib.aiohttp import status
from simcore_postgres_database.models.products import ProductLoginSettingsDict, products
from simcore_service_webserver.application_settings import ApplicationSettings
from simcore_service_webserver.login._auth_handlers import CodePageParams, NextPage
from simcore_service_webserver.login._constants import CODE_2FA_SMS_CODE_REQUIRED


@pytest.fixture
def app_environment(app_environment: EnvVarsDict, monkeypatch: pytest.MonkeyPatch):
    envs_login = setenvs_from_dict(
        monkeypatch,
        {
            "LOGIN_REGISTRATION_CONFIRMATION_REQUIRED": "1",
            "LOGIN_REGISTRATION_INVITATION_REQUIRED": "0",
            "LOGIN_2FA_CODE_EXPIRATION_SEC": "60",
        },
    )

    print(ApplicationSettings.create_from_envs().model_dump_json(indent=2))

    return {**app_environment, **envs_login}


@pytest.fixture
def postgres_db(postgres_db: sa.engine.Engine):
    # adds fake twilio_messaging_sid in osparc product (pre-initialized)
    stmt = (
        products.update()
        .values(
            twilio_messaging_sid="x" * 34,
            login_settings=ProductLoginSettingsDict(
                LOGIN_2FA_REQUIRED=True
            ),  # <--- 2FA Enabled for product
        )
        .where(products.c.name == "osparc")
    )
    with postgres_db.connect() as conn:
        conn.execute(stmt)
    return postgres_db


async def test_resend_2fa_entrypoint_is_protected(
    client: TestClient,
    fake_user_email: str,
):
    assert client.app

    url = client.app.router["auth_resend_2fa_code"].url_for()
    response = await client.post(
        f"{url}",
        json={
            "email": fake_user_email,
            "send_as": "SMS",
        },
    )

    # protected
    assert response.status == status.HTTP_401_UNAUTHORIZED


async def test_resend_2fa_workflow(
    client: TestClient,
    registered_user: UserInfoDict,
    mocker: MockFixture,
):
    assert client.app

    # spy send functions
    mock_send_sms_code1 = mocker.patch(
        "simcore_service_webserver.login._2fa_handlers.send_sms_code", autospec=True
    )
    mock_send_sms_code2 = mocker.patch(
        "simcore_service_webserver.login._auth_handlers.send_sms_code", autospec=True
    )

    mock_send_email_code = mocker.patch(
        "simcore_service_webserver.login._2fa_handlers.send_email_code", autospec=True
    )

    mock_get_2fa_code = mocker.patch(
        "simcore_service_webserver.login._2fa_handlers.get_2fa_code",
        autospec=True,
        return_value=None,  # <-- Emulates code expired
    )

    # login
    url = client.app.router["auth_login"].url_for()
    response = await client.post(
        f"{url}",
        json={
            "email": registered_user["email"],
            "password": registered_user["raw_password"],
        },
    )
    data, _ = await assert_status(response, status.HTTP_202_ACCEPTED)
    next_page = NextPage[CodePageParams].model_validate(data)
    assert next_page.name == CODE_2FA_SMS_CODE_REQUIRED
    assert next_page.parameters.expiration_2fa > 0

    # resend code via SMS
    url = client.app.router["auth_resend_2fa_code"].url_for()
    response = await client.post(
        f"{url}",
        json={
            "email": registered_user["email"],
            "via": "SMS",
        },
    )

    data, error = await assert_status(response, status.HTTP_200_OK)
    assert data["name"]
    assert data["parameters"]
    assert data["parameters"]["message"]
    assert data["parameters"]["expiration_2fa"]
    assert not error

    assert mock_get_2fa_code.call_count == 1, "Emulates code expired"
    assert mock_send_sms_code2.call_count == 1, "SMS was not sent??"

    # resend code via email
    response = await client.post(
        f"{url}",
        json={
            "email": registered_user["email"],
            "via": "Email",
        },
    )

    data, error = await assert_status(response, status.HTTP_200_OK)
    assert data["name"]
    assert data["parameters"]
    assert data["parameters"]["message"]
    assert data["parameters"]["expiration_2fa"]
    assert not error

    assert mock_get_2fa_code.call_count == 2, "Emulates code expired"
    assert mock_send_email_code.call_count == 1, "Email was not sent??"
