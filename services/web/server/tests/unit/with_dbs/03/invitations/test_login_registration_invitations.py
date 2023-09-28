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
from pytest_simcore.helpers.utils_envs import EnvVarsDict, setenvs_from_dict
from simcore_service_webserver.login.handlers_registration import (
    InvitationCheck,
    InvitationInfo,
)
from simcore_service_webserver.login.settings import LoginSettingsForProduct


@pytest.fixture
def app_environment(
    app_environment: EnvVarsDict,
    env_devel_dict: EnvVarsDict,
    monkeypatch: pytest.MonkeyPatch,
) -> EnvVarsDict:
    login_envs = setenvs_from_dict(
        monkeypatch,
        {
            "LOGIN_REGISTRATION_CONFIRMATION_REQUIRED": "1",
            "LOGIN_REGISTRATION_INVITATION_REQUIRED": "0",
            "LOGIN_2FA_CODE_EXPIRATION_SEC": "60",
        },
    )

    # set INVITATIONS_* variables using those in .devel-env
    invitation_envs = setenvs_from_dict(
        monkeypatch,
        envs={
            name: value
            for name, value in env_devel_dict.items()
            if name.startswith("INVITATIONS_")
        },
    )

    return app_environment | login_envs | invitation_envs


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
    assert invitation.email == None


async def test_check_registration_invitations_with_old_code(
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


@pytest.mark.acceptance_test
async def test_check_registration_invitation_and_get_email(
    client: TestClient,
    mocker: MockerFixture,
    mock_invitations_service_http_api: AioResponsesMock,
    expected_invitation: ApiInvitationContent,
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
        f"{url}", json=InvitationCheck(invitation="*" * 105).dict()
    )
    data, _ = await assert_status(response, web.HTTPOk)

    invitation = InvitationInfo.parse_obj(data)
    assert invitation.email == expected_invitation.guest
