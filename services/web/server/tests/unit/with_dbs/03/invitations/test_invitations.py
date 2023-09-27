# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from datetime import datetime, timezone

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient
from faker import Faker
from models_library.api_schemas_webserver.product import InvitationGenerated
from pytest_simcore.aioresponses_mocker import AioResponsesMock
from pytest_simcore.helpers.utils_assert import assert_status
from pytest_simcore.helpers.utils_envs import EnvVarsDict, setenvs_from_dict
from pytest_simcore.helpers.utils_login import NewUser, UserInfoDict
from simcore_postgres_database.models.users import UserRole
from simcore_service_webserver.application_settings import ApplicationSettings
from simcore_service_webserver.invitations._client import (
    InvitationContent,
    InvitationsServiceApi,
    get_invitations_service_api,
)
from simcore_service_webserver.invitations.errors import (
    InvalidInvitation,
    InvitationsServiceUnavailable,
)
from simcore_service_webserver.invitations.plugin import validate_invitation_url
from yarl import URL


@pytest.fixture
def app_environment(
    app_environment: EnvVarsDict,
    env_devel_dict: EnvVarsDict,
    monkeypatch: pytest.MonkeyPatch,
):
    envs_plugins = setenvs_from_dict(
        monkeypatch,
        {
            "WEBSERVER_ACTIVITY": "null",
            "WEBSERVER_NOTIFICATIONS": "0",
            "WEBSERVER_DIAGNOSTICS": "null",
            "WEBSERVER_EXPORTER": "null",
            "WEBSERVER_GARBAGE_COLLECTOR": "null",
            "WEBSERVER_META_MODELING": "0",
            "WEBSERVER_PUBLICATIONS": "0",
            "WEBSERVER_REMOTE_DEBUG": "0",
            "WEBSERVER_SOCKETIO": "0",
            "WEBSERVER_STUDIES_ACCESS_ENABLED": "0",
            "WEBSERVER_TAGS": "0",
            "WEBSERVER_TRACING": "null",
            "WEBSERVER_VERSION_CONTROL": "0",
            "WEBSERVER_WALLETS": "0",
        },
    )

    # undefine WEBSERVER_INVITATIONS
    app_environment.pop("WEBSERVER_INVITATIONS", None)
    monkeypatch.delenv("WEBSERVER_INVITATIONS", raising=False)

    # set INVITATIONS_* variables using those in .devel-env
    envs_invitations = setenvs_from_dict(
        monkeypatch,
        envs={
            name: value
            for name, value in env_devel_dict.items()
            if name.startswith("INVITATIONS_")
        },
    )

    print(ApplicationSettings.create_from_envs().json(indent=2))
    return app_environment | envs_plugins | envs_invitations


async def test_invitation_service_unavailable(
    client: TestClient,
    expected_invitation: InvitationContent,
):
    assert client.app
    invitations_api: InvitationsServiceApi = get_invitations_service_api(app=client.app)

    assert not await invitations_api.ping()

    with pytest.raises(InvitationsServiceUnavailable):
        await validate_invitation_url(
            app=client.app,
            guest_email=expected_invitation.guest,
            invitation_url="https://server.com#/registration?invitation=1234",
        )


async def test_invitation_service_api_ping(
    client: TestClient,
    mock_invitations_service_http_api: AioResponsesMock,
    base_url: URL,
):
    invitations_api: InvitationsServiceApi = get_invitations_service_api(app=client.app)

    print(mock_invitations_service_http_api)

    # first request is mocked to pass
    assert await invitations_api.ping()

    # second request is mocked to fail (since mock only works once)
    assert not await invitations_api.is_responsive()


async def test_valid_invitation(
    client: TestClient,
    mock_invitations_service_http_api: AioResponsesMock,
    expected_invitation: InvitationContent,
):
    assert client.app
    invitation = await validate_invitation_url(
        app=client.app,
        guest_email=expected_invitation.guest,
        invitation_url="https://server.com#register?invitation=1234",
    )
    assert invitation
    assert invitation == expected_invitation


async def test_invalid_invitation_if_guest_is_already_registered(
    client: TestClient,
    mock_invitations_service_http_api: AioResponsesMock,
    expected_invitation: InvitationContent,
):
    assert client.app
    async with NewUser(
        params={
            "name": "test-user",
            "email": expected_invitation.guest,
        },
        app=client.app,
    ):
        with pytest.raises(InvalidInvitation):
            await validate_invitation_url(
                app=client.app,
                guest_email=expected_invitation.guest,
                invitation_url="https://server.com#register?invitation=1234",
            )


async def test_invalid_invitation_if_not_guest(
    client: TestClient,
    mock_invitations_service_http_api: AioResponsesMock,
    expected_invitation: InvitationContent,
):
    assert client.app
    assert expected_invitation.guest != "unexpected_guest@email.me"
    with pytest.raises(InvalidInvitation):
        await validate_invitation_url(
            app=client.app,
            guest_email="unexpected_guest@email.me",
            invitation_url="https://server.com#register?invitation=1234",
        )


@pytest.mark.testit
@pytest.mark.parametrize(
    "user_role,expected_status",
    [
        (UserRole.ANONYMOUS, web.HTTPUnauthorized),
        (UserRole.GUEST, web.HTTPForbidden),
        (UserRole.USER, web.HTTPForbidden),
        (UserRole.TESTER, web.HTTPForbidden),
        (UserRole.PRODUCT_OWNER, web.HTTPOk),
        (UserRole.ADMIN, web.HTTPOk),
    ],
)
async def test_product_owner_generate_invitation(
    client: TestClient,
    mock_invitations_service_http_api: AioResponsesMock,
    faker: Faker,
    logged_user: UserInfoDict,
    expected_status: type[web.HTTPException],
):
    before_dt = datetime.now(tz=timezone.utc)
    guest_email = faker.email()
    trial_account_days = 3

    # request
    response = await client.post(
        "/v0/invitation:generate",
        json={
            "guest": guest_email,
            "trialAccountDays": trial_account_days,
        },
    )

    # checks
    data, error = await assert_status(response, expected_status)
    if data:
        got = InvitationGenerated.parse_obj(data)
        expected_data = {
            "issuer": logged_user["email"],
            "guest": guest_email,
            "trialAccountDays": trial_account_days,
        }
        assert got.dict(include=set(expected_data)) == expected_data

        product_base_url = f"{client.make_url('/')}"
        assert got.invitation_link.startswith(product_base_url)
        assert before_dt < got.created
        assert got.created < datetime.now(tz=timezone.utc)
    else:
        assert error
