# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import asyncio
from datetime import timedelta

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
from faker import Faker
from pytest import CaptureFixture
from pytest_mock import MockerFixture
from pytest_simcore.helpers.utils_assert import assert_error, assert_status
from pytest_simcore.helpers.utils_login import NewInvitation, NewUser, parse_link
from servicelib.aiohttp.rest_responses import unwrap_envelope
from simcore_service_webserver.db_models import ConfirmationAction, UserStatus
from simcore_service_webserver.login._confirmation import _url_for_confirmation
from simcore_service_webserver.login._constants import MSG_PASSWORD_MISMATCH
from simcore_service_webserver.login._registration import (
    InvitationData,
    get_confirmation_info,
)
from simcore_service_webserver.login.settings import LoginOptions, LoginSettings
from simcore_service_webserver.login.storage import AsyncpgStorage
from simcore_service_webserver.users_models import ProfileGet


@pytest.fixture
def client(
    event_loop: asyncio.AbstractEventLoop,
    aiohttp_client,
    web_server: TestServer,
    mock_orphaned_services,
) -> TestClient:
    client_ = event_loop.run_until_complete(aiohttp_client(web_server))
    return client_


async def test_regiter_entrypoint(
    client: TestClient, fake_user_email: str, fake_user_password: str
):
    assert client.app
    url = client.app.router["auth_register"].url_for()
    response = await client.post(
        f"{url}",
        json={
            "email": fake_user_email,
            "password": fake_user_password,
            "confirm": fake_user_password,
        },
    )

    data, _ = await assert_status(response, web.HTTPOk)
    assert fake_user_email in data["message"]


async def test_register_body_validation(client: TestClient, fake_user_password: str):
    assert client.app
    url = client.app.router["auth_register"].url_for()
    response = await client.post(
        f"{url}",
        json={
            "email": "not-an-email",
            "password": fake_user_password,
            "confirm": fake_user_password.upper(),
        },
    )

    assert response.status == web.HTTPUnprocessableEntity.status_code
    body = await response.json()
    data, error = unwrap_envelope(body)

    assert data is None
    assert error == {
        "status": 422,
        "errors": [
            {
                "code": "value_error.email",
                "message": "value is not a valid email address",
                "resource": "/v0/auth/register",
                "field": "email",
            },
            {
                "code": "value_error",
                "message": MSG_PASSWORD_MISMATCH,
                "resource": "/v0/auth/register",
                "field": "confirm",
            },
        ],
    }


async def test_regitration_is_not_get(client: TestClient):
    assert client.app
    url = client.app.router["auth_register"].url_for()
    r = await client.get(f"{url}")
    await assert_error(r, web.HTTPMethodNotAllowed)


async def test_registration_with_existing_email(
    client: TestClient, login_options: LoginOptions
):
    assert client.app
    url = client.app.router["auth_register"].url_for()
    async with NewUser(app=client.app) as user:
        r = await client.post(
            f"{url}",
            json={
                "email": user["email"],
                "password": user["raw_password"],
                "confirm": user["raw_password"],
            },
        )
    await assert_error(r, web.HTTPConflict, login_options.MSG_EMAIL_EXISTS)


@pytest.mark.skip("TODO: Feature still not implemented")
async def test_registration_with_expired_confirmation(
    client: TestClient,
    login_options: LoginOptions,
    db: AsyncpgStorage,
    mocker: MockerFixture,
):
    assert client.app
    mocker.patch(
        "simcore_service_webserver.login.handlers_registration.get_plugin_settings",
        autospec=True,
        return_value=LoginSettings(
            LOGIN_REGISTRATION_CONFIRMATION_REQUIRED=True,
            LOGIN_REGISTRATION_INVITATION_REQUIRED=True,
            LOGIN_TWILIO=None,
        ),
    )

    url = client.app.router["auth_register"].url_for()

    async with NewUser({"status": UserStatus.CONFIRMATION_PENDING.name}) as user:
        confirmation = await db.create_confirmation(
            user["id"], ConfirmationAction.REGISTRATION.name
        )
        r = await client.post(
            f"{url}",
            json={
                "email": user["email"],
                "password": user["raw_password"],
                "confirm": user["raw_password"],
            },
        )
        await db.delete_confirmation(confirmation)

    await assert_error(r, web.HTTPConflict, login_options.MSG_EMAIL_EXISTS)


async def test_registration_with_invalid_confirmation_code(
    client: TestClient,
    login_options: LoginOptions,
    db: AsyncpgStorage,
    mocker: MockerFixture,
):
    # Checks bug in https://github.com/ITISFoundation/osparc-simcore/pull/3356
    assert client.app
    mocker.patch(
        "simcore_service_webserver.login.settings.get_plugin_settings",
        autospec=True,
        return_value=LoginSettings(
            LOGIN_REGISTRATION_CONFIRMATION_REQUIRED=True,
            LOGIN_REGISTRATION_INVITATION_REQUIRED=False,
            LOGIN_TWILIO=None,
        ),
    )

    confirmation_link = _url_for_confirmation(
        client.app, code="INVALID_CONFIRMATION_CODE"
    )
    r = await client.get(f"{confirmation_link}")

    # Invalid code redirect to root without any error to the login page
    #
    assert r.ok
    assert f"{r.url.relative()}" == login_options.LOGIN_REDIRECT
    assert r.history[0].status == web.HTTPFound.status_code


async def test_registration_without_confirmation(
    client: TestClient,
    login_options: LoginOptions,
    db: AsyncpgStorage,
    mocker: MockerFixture,
    fake_user_email: str,
    fake_user_password: str,
):
    assert client.app
    mocker.patch(
        "simcore_service_webserver.login.handlers_registration.get_plugin_settings",
        autospec=True,
        return_value=LoginSettings(
            LOGIN_REGISTRATION_CONFIRMATION_REQUIRED=False,
            LOGIN_REGISTRATION_INVITATION_REQUIRED=False,
            LOGIN_TWILIO=None,
        ),
    )

    url = client.app.router["auth_register"].url_for()
    r = await client.post(
        f"{url}",
        json={
            "email": fake_user_email,
            "password": fake_user_password,
            "confirm": fake_user_password,
        },
    )
    data, error = unwrap_envelope(await r.json())

    assert r.status == 200, (data, error)
    assert login_options.MSG_LOGGED_IN in data["message"]

    user = await db.get_user({"email": fake_user_email})
    assert user
    await db.delete_user(user)


async def test_registration_with_confirmation(
    client: TestClient,
    login_options: LoginOptions,
    db: AsyncpgStorage,
    capsys: CaptureFixture,
    mocker: MockerFixture,
    fake_user_email: str,
    fake_user_password: str,
):
    assert client.app
    mocker.patch(
        "simcore_service_webserver.login.handlers_registration.get_plugin_settings",
        autospec=True,
        return_value=LoginSettings(
            LOGIN_REGISTRATION_CONFIRMATION_REQUIRED=True,
            LOGIN_REGISTRATION_INVITATION_REQUIRED=False,
            LOGIN_TWILIO=None,
        ),
    )

    url = client.app.router["auth_register"].url_for()
    r = await client.post(
        f"{url}",
        json={
            "email": fake_user_email,
            "password": fake_user_password,
            "confirm": fake_user_password,
        },
    )
    data, error = unwrap_envelope(await r.json())
    assert r.status == 200, (data, error)

    user = await db.get_user({"email": fake_user_email})
    assert user["status"] == UserStatus.CONFIRMATION_PENDING.name

    assert "verification link" in data["message"]

    # retrieves sent link by email (see monkeypatch of email in conftest.py)
    out, _ = capsys.readouterr()
    confirmation_url = parse_link(out)
    assert "/auth/confirmation/" in str(confirmation_url)
    resp = await client.get(confirmation_url)
    text = await resp.text()

    assert (
        "This is a result of disable_static_webserver fixture for product OSPARC"
        in text
    )
    assert resp.status == 200

    # user is active
    user = await db.get_user({"email": fake_user_email})
    assert user["status"] == UserStatus.ACTIVE.name

    # cleanup
    await db.delete_user(user)


@pytest.mark.parametrize(
    "is_invitation_required,has_valid_invitation,expected_response",
    [
        (True, True, web.HTTPOk),
        (True, False, web.HTTPForbidden),
        (False, True, web.HTTPOk),
        (False, False, web.HTTPOk),
    ],
)
async def test_registration_with_invitation(
    client: TestClient,
    login_options: LoginOptions,
    db: AsyncpgStorage,
    is_invitation_required: bool,
    has_valid_invitation: bool,
    expected_response: type[web.HTTPError],
    mocker: MockerFixture,
    fake_user_email: str,
    fake_user_password: str,
):
    assert client.app
    mocker.patch(
        "simcore_service_webserver.login.handlers_registration.get_plugin_settings",
        autospec=True,
        return_value=LoginSettings(
            LOGIN_REGISTRATION_CONFIRMATION_REQUIRED=False,
            LOGIN_REGISTRATION_INVITATION_REQUIRED=is_invitation_required,
            LOGIN_TWILIO=None,
        ),
    )

    #
    # User gets an email with a link as
    #   https:/some-web-address.io/#/registration/?invitation={code}
    #
    # Front end then creates the following request
    #
    async with NewInvitation(client) as f:
        confirmation = f.confirmation
        assert confirmation

        print(get_confirmation_info(login_options, confirmation))

        url = client.app.router["auth_register"].url_for()

        r = await client.post(
            f"{url}",
            json={
                "email": fake_user_email,
                "password": fake_user_password,
                "confirm": fake_user_password,
                "invitation": confirmation["code"]
                if has_valid_invitation
                else "WRONG_CODE",
            },
        )
        await assert_status(r, expected_response)

        # check optional fields in body
        if not has_valid_invitation and not is_invitation_required:
            r = await client.post(
                f"{url}",
                json={
                    "email": "new-user" + fake_user_email,
                    "password": fake_user_password,
                },
            )
            await assert_status(r, expected_response)

        if is_invitation_required and has_valid_invitation:
            assert not await db.get_confirmation(confirmation)


async def test_registraton_with_invitation_for_trial_account(
    client: TestClient,
    login_options: LoginOptions,
    faker: Faker,
    mocker: MockerFixture,
    fake_user_email: str,
    fake_user_password: str,
):
    assert client.app
    mocker.patch(
        "simcore_service_webserver.login.handlers_registration.get_plugin_settings",
        autospec=True,
        return_value=LoginSettings(
            LOGIN_REGISTRATION_CONFIRMATION_REQUIRED=False,
            LOGIN_REGISTRATION_INVITATION_REQUIRED=True,
            LOGIN_TWILIO=None,
        ),
    )

    # User story:
    # 1. app-team creates an invitation link for a trial account
    # 2. user clicks the invitation link
    #   - redirects to the registration page
    # 3. user fills the registration and presses OK
    #   - requests API 'auth_register' w/ invitation code (passed in the invitation link above)
    #   - trial account is created:
    #         - invitation is validated
    #         - expiration date = created_at + trial_days (in invitation)
    #         - creates a user with an expiration date
    # 4. user can login
    # 5. GET profile response includes expiration date
    #

    # (1) creates a invitation to register a TRIAL account
    TRIAL_DAYS = 1
    async with NewInvitation(
        client, guest_email=faker.email(), trial_days=TRIAL_DAYS
    ) as invitation:
        assert invitation.confirmation

        # checks that invitation is correct
        info = get_confirmation_info(login_options, invitation.confirmation)
        print(info)
        assert info["data"]
        assert isinstance(info["data"], InvitationData)

        # (3) use register using the invitation code
        url = client.app.router["auth_register"].url_for()
        r = await client.post(
            f"{url}",
            json={
                "email": fake_user_email,
                "password": fake_user_password,
                "confirm": fake_user_password,
                "invitation": invitation.confirmation["code"],
            },
        )
        await assert_status(r, web.HTTPOk)

        # (4) login
        url = client.app.router["auth_login"].url_for()
        r = await client.post(
            f"{url}",
            json={
                "email": fake_user_email,
                "password": fake_user_password,
            },
        )
        await assert_status(r, web.HTTPOk)

        # (5) get profile
        url = client.app.router["get_my_profile"].url_for()
        r = await client.get(f"{url}")
        data, _ = await assert_status(r, web.HTTPOk)
        profile = ProfileGet.parse_obj(data)

        expected = invitation.user["created_at"] + timedelta(days=TRIAL_DAYS)
        assert profile.expiration_date
        assert profile.expiration_date == expected.date()
