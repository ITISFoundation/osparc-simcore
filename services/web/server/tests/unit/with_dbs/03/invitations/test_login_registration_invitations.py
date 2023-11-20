# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient
from models_library.api_schemas_invitations.invitations import ApiInvitationContent
from pytest_mock import MockerFixture
from pytest_simcore.aioresponses_mocker import AioResponsesMock
from pytest_simcore.helpers.utils_assert import assert_status
from simcore_service_webserver.login.handlers_registration import (
    InvitationCheck,
    InvitationInfo,
)
from simcore_service_webserver.login.settings import LoginSettingsForProduct


async def test_check_registration_invitation_when_not_required(
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
    assert invitation.email is None


async def test_check_registration_invitations_with_old_code(
    client: TestClient,
    mocker: MockerFixture,
):
    assert client.app
    mocker.patch(
        "simcore_service_webserver.login.handlers_registration.get_plugin_settings",
        autospec=True,
        return_value=LoginSettingsForProduct.create_from_envs(
            LOGIN_REGISTRATION_INVITATION_REQUIRED=True,  # <--
        ),
    )

    url = client.app.router["auth_check_registration_invitation"].url_for()
    response = await client.post(
        f"{url}", json=InvitationCheck(invitation="short-code").dict()
    )
    data, _ = await assert_status(response, web.HTTPOk)

    invitation = InvitationInfo.parse_obj(data)
    assert invitation.email is None


@pytest.mark.acceptance_test()
async def test_check_registration_invitation_and_get_email(
    client: TestClient,
    mocker: MockerFixture,
    mock_invitations_service_http_api: AioResponsesMock,
    fake_osparc_invitation: ApiInvitationContent,
):
    assert client.app
    mocker.patch(
        "simcore_service_webserver.login.handlers_registration.get_plugin_settings",
        autospec=True,
        return_value=LoginSettingsForProduct.create_from_envs(
            LOGIN_REGISTRATION_INVITATION_REQUIRED=True,  # <--
        ),
    )

    url = client.app.router["auth_check_registration_invitation"].url_for()
    response = await client.post(
        f"{url}", json=InvitationCheck(invitation="*" * 105).dict()
    )
    data, _ = await assert_status(response, web.HTTPOk)

    invitation = InvitationInfo.parse_obj(data)
    assert invitation.email == fake_osparc_invitation.guest
