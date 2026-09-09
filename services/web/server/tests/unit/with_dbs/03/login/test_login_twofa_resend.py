# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import pytest
import sqlalchemy as sa
from aiohttp.test_utils import TestClient
from pytest_mock import MockFixture
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.webserver_users import UserInfoDict
from servicelib.aiohttp import status
from simcore_service_webserver.login._controller.rest.auth_schemas import (
    CodePageParams,
    NextPage,
)
from simcore_service_webserver.login.constants import CODE_2FA_SMS_CODE_REQUIRED


@pytest.fixture
def postgres_db(postgres_db_with_2fa_enabled_for_osparc: sa.engine.Engine) -> sa.engine.Engine:
    return postgres_db_with_2fa_enabled_for_osparc


async def test_resend_2fa_entrypoint_is_protected(
    client: TestClient,
    user_email: str,
):
    assert client.app

    url = client.app.router["auth_resend_2fa_code"].url_for()
    response = await client.post(
        f"{url}",
        json={
            "email": user_email,
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

    # patch send functions
    mock_send_sms_code_1 = mocker.patch(
        "simcore_service_webserver.login._controller.rest.twofa._twofa_service.send_sms_code",
        autospec=True,
    )
    mock_send_sms_code_2 = mocker.patch(
        "simcore_service_webserver.login._controller.rest.auth._twofa_service.send_sms_code",
        # NOTE: When importing the full submodule, we are mocking _twofa_service
        #  from .. import _twofa_service
        #  _twofa_service.send_sms_code(...)
        new=mock_send_sms_code_1,
    )

    mock_send_email_code = mocker.patch(
        "simcore_service_webserver.login._controller.rest.twofa._twofa_service.send_email_code",
        autospec=True,
    )

    mock_get_2fa_code = mocker.patch(
        "simcore_service_webserver.login._controller.rest.twofa._twofa_service.get_2fa_code",
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

    assert next_page.parameters is not None
    assert next_page.parameters.expiration_2fa is not None
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
    assert mock_send_sms_code_2.call_count == 2, "SMS was not sent??"

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
