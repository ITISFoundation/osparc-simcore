# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from aiohttp import web
from aiohttp.test_utils import TestClient
from pytest_mock import MockerFixture
from pytest_simcore.helpers.utils_assert import assert_status
from simcore_service_webserver.login.handlers_registration import (
    InvitationCheck,
    InvitationInfo,
)
from simcore_service_webserver.login.settings import LoginSettingsForProduct


async def test_check_registration_invitation(
    client: TestClient,
    mocker: MockerFixture,
):
    assert client.app
    mocker.patch(
        "simcore_service_webserver.login.handlers_registration.get_plugin_settings",
        autospec=True,
        return_value=LoginSettingsForProduct(
            LOGIN_REGISTRATION_CONFIRMATION_REQUIRED=False,
            LOGIN_REGISTRATION_INVITATION_REQUIRED=False,
            LOGIN_TWILIO=None,
        ),
    )

    url = client.app.router["auth_check_registration_invitation"].url_for()
    response = await client.post(
        f"{url}", json=InvitationCheck(invitation="*" * 100).dict()
    )
    data, _ = await assert_status(response, web.HTTPOk)

    invitation = InvitationInfo.parse_obj(data)
    assert invitation.email == None


async def test_check_registration_invitation_2(
    client: TestClient,
    mocker: MockerFixture,
):
    assert client.app
    mocker.patch(
        "simcore_service_webserver.login.handlers_registration.get_plugin_settings",
        autospec=True,
        return_value=LoginSettingsForProduct(
            LOGIN_REGISTRATION_INVITATION_REQUIRED=True,  # <--
        ),
    )

    url = client.app.router["auth_check_registration_invitation"].url_for()
    response = await client.post(
        f"{url}", json=InvitationCheck(invitation="short-code").dict()
    )
    data, _ = await assert_status(response, web.HTTPOk)

    invitation = InvitationInfo.parse_obj(data)
    assert invitation.email == None
    # TODO: LOGIN_REGISTRATION_INVITATION_REQUIRED = True

    # TODO: use `mock_invitations_service_http_api` already in test_invitations.py!
