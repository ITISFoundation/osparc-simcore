# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from datetime import timedelta
from http import HTTPStatus

import pytest
from aiohttp.test_utils import TestClient
from faker import Faker
from models_library.products import ProductName
from pytest_mock import MockerFixture
from pytest_simcore.helpers.assert_checks import assert_error, assert_status
from pytest_simcore.helpers.monkeypatch_envs import EnvVarsDict, setenvs_from_dict
from pytest_simcore.helpers.webserver_login import NewInvitation, NewUser, parse_link
from servicelib.aiohttp import status
from servicelib.aiohttp.rest_responses import unwrap_envelope
from simcore_service_webserver.db.models import UserStatus
from simcore_service_webserver.groups.api import auto_add_user_to_product_group
from simcore_service_webserver.login._confirmation import _url_for_confirmation
from simcore_service_webserver.login._constants import (
    MSG_EMAIL_ALREADY_REGISTERED,
    MSG_LOGGED_IN,
    MSG_PASSWORD_MISMATCH,
    MSG_WEAK_PASSWORD,
)
from simcore_service_webserver.login.settings import (
    LoginOptions,
    LoginSettingsForProduct,
    get_plugin_settings,
)
from simcore_service_webserver.login.storage import AsyncpgStorage
from simcore_service_webserver.users.schemas import ProfileGet


@pytest.fixture
def app_environment(
    app_environment: EnvVarsDict, monkeypatch: pytest.MonkeyPatch
) -> EnvVarsDict:
    login_envs = setenvs_from_dict(
        monkeypatch,
        {
            "LOGIN_REGISTRATION_CONFIRMATION_REQUIRED": "1",
            "LOGIN_REGISTRATION_INVITATION_REQUIRED": "0",
            "LOGIN_2FA_CODE_EXPIRATION_SEC": "60",
        },
    )

    return app_environment | login_envs


async def test_register_entrypoint(
    client: TestClient,
    fake_user_email: str,
    fake_user_password: str,
    cleanup_db_tables: None,
):
    assert client.app
    url = client.app.router["auth_register"].url_for()
    assert url.path == "/v0/auth/register"
    response = await client.post(
        url.path,
        json={
            "email": fake_user_email,
            "password": fake_user_password,
            "confirm": fake_user_password,
        },
    )

    data, _ = await assert_status(response, status.HTTP_200_OK)
    assert fake_user_email in data["message"]


async def test_register_body_validation(
    client: TestClient, fake_user_password: str, cleanup_db_tables: None
):
    assert client.app
    url = client.app.router["auth_register"].url_for()
    response = await client.post(
        url.path,
        json={
            "email": "not-an-email",
            "password": fake_user_password,
            "confirm": fake_user_password.upper(),
        },
    )

    assert response.status == status.HTTP_422_UNPROCESSABLE_ENTITY
    body = await response.json()
    data, error = unwrap_envelope(body)

    assert data is None
    assert error == {
        "status": 422,
        "errors": [
            {
                "code": "value_error",
                "message": "value is not a valid email address: An email address must have an @-sign.",
                "resource": "/v0/auth/register",
                "field": "email",
            },
            {
                "code": "value_error",
                "message": f"Value error, {MSG_PASSWORD_MISMATCH}",
                "resource": "/v0/auth/register",
                "field": "confirm",
            },
        ],
    }


async def test_registration_is_not_get(client: TestClient):
    assert client.app
    url = client.app.router["auth_register"].url_for()
    response = await client.get(url.path)
    await assert_error(response, status.HTTP_405_METHOD_NOT_ALLOWED)


async def test_registration_with_registered_user(
    client: TestClient, default_product_name: ProductName, cleanup_db_tables: None
):
    assert client.app

    async with NewUser(app=client.app) as user:
        await auto_add_user_to_product_group(
            client.app, user_id=user["id"], product_name=default_product_name
        )

        url = client.app.router["auth_register"].url_for()
        response = await client.post(
            url.path,
            json={
                "email": user["email"],
                "password": user["raw_password"],
                "confirm": user["raw_password"],
            },
        )
    await assert_error(response, status.HTTP_409_CONFLICT, MSG_EMAIL_ALREADY_REGISTERED)


async def test_registration_invitation_stays_valid_if_once_tried_with_weak_password(
    client: TestClient,
    login_options: LoginOptions,
    db: AsyncpgStorage,
    mocker: MockerFixture,
    fake_user_email: str,
    fake_user_password: str,
    default_product_name: ProductName,
    fake_weak_password: str,
    cleanup_db_tables: None,
):
    assert client.app
    mocker.patch(
        "simcore_service_webserver.login.handlers_registration.get_plugin_settings",
        autospec=True,
        return_value=LoginSettingsForProduct(
            LOGIN_REGISTRATION_CONFIRMATION_REQUIRED=False,
            LOGIN_REGISTRATION_INVITATION_REQUIRED=True,
            LOGIN_TWILIO=None,
        ),
    )

    #
    # User gets an email with a link as
    #   https:/some-web-address.io/#/registration/?invitation={code}
    #
    # Front end then creates the following request
    #
    session_plugin_settings = get_plugin_settings(client.app, default_product_name)
    async with NewInvitation(client) as f:
        confirmation = f.confirmation
        assert confirmation

        url = client.app.router["auth_register"].url_for()

        response = await client.post(
            url.path,
            json={
                "email": fake_user_email,
                "password": fake_weak_password,
                "confirm": fake_weak_password,
                "invitation": confirmation["code"],
            },
        )
        await assert_error(
            response,
            status.HTTP_401_UNAUTHORIZED,
            MSG_WEAK_PASSWORD.format(
                LOGIN_PASSWORD_MIN_LENGTH=session_plugin_settings.LOGIN_PASSWORD_MIN_LENGTH
            ),
        )
        response = await client.post(
            url.path,
            json={
                "email": fake_user_email,
                "password": fake_user_password,
                "confirm": fake_user_password,
                "invitation": confirmation["code"],
            },
        )
        assert not await db.get_confirmation(confirmation)


async def test_registration_with_weak_password_fails(
    client: TestClient,
    mocker: MockerFixture,
    cleanup_db_tables: None,
    default_product_name: ProductName,
    fake_user_email: str,
    fake_weak_password: str,
):
    assert client.app
    url = client.app.router["auth_register"].url_for()
    login_settings = get_plugin_settings(client.app, default_product_name)
    response = await client.post(
        url.path,
        json={
            "email": fake_user_email,
            "password": fake_weak_password,
            "confirm": fake_weak_password,
        },
    )
    await assert_error(
        response,
        status.HTTP_401_UNAUTHORIZED,
        MSG_WEAK_PASSWORD.format(
            LOGIN_PASSWORD_MIN_LENGTH=login_settings.LOGIN_PASSWORD_MIN_LENGTH
        ),
    )


async def test_registration_with_invalid_confirmation_code(
    client: TestClient,
    login_options: LoginOptions,
    db: AsyncpgStorage,
    mocker: MockerFixture,
    cleanup_db_tables: None,
):
    # Checks bug in https://github.com/ITISFoundation/osparc-simcore/pull/3356
    assert client.app
    mocker.patch(
        "simcore_service_webserver.login.settings.get_plugin_settings",
        autospec=True,
        return_value=LoginSettingsForProduct(
            LOGIN_REGISTRATION_CONFIRMATION_REQUIRED=True,
            LOGIN_REGISTRATION_INVITATION_REQUIRED=False,  # <----- NO invitation
            LOGIN_TWILIO=None,
        ),
    )

    confirmation_link = _url_for_confirmation(
        client.app, code="INVALID_CONFIRMATION_CODE"
    )
    response = await client.get(f"{confirmation_link}")

    # Invalid code redirect to root without any error to the login page
    assert response.ok
    assert f"{response.url.relative()}" == login_options.LOGIN_REDIRECT
    assert response.history[0].status == status.HTTP_302_FOUND


async def test_registration_without_confirmation(
    client: TestClient,
    db: AsyncpgStorage,
    mocker: MockerFixture,
    fake_user_email: str,
    fake_user_password: str,
    cleanup_db_tables: None,
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

    url = client.app.router["auth_register"].url_for()
    response = await client.post(
        url.path,
        json={
            "email": fake_user_email,
            "password": fake_user_password,
            "confirm": fake_user_password,
        },
    )

    data, _ = await assert_status(response, status.HTTP_200_OK)
    assert MSG_LOGGED_IN in data["message"]

    user = await db.get_user({"email": fake_user_email})
    assert user


async def test_registration_with_confirmation(
    client: TestClient,
    db: AsyncpgStorage,
    capsys: pytest.CaptureFixture,
    mocker: MockerFixture,
    fake_user_email: str,
    fake_user_password: str,
    mocked_email_core_remove_comments: None,
    cleanup_db_tables: None,
):
    assert client.app
    mocker.patch(
        "simcore_service_webserver.login.handlers_registration.get_plugin_settings",
        autospec=True,
        return_value=LoginSettingsForProduct(
            LOGIN_REGISTRATION_CONFIRMATION_REQUIRED=True,
            LOGIN_REGISTRATION_INVITATION_REQUIRED=False,
            LOGIN_TWILIO=None,
        ),
    )

    # login
    url = client.app.router["auth_register"].url_for()
    response = await client.post(
        url.path,
        json={
            "email": fake_user_email,
            "password": fake_user_password,
            "confirm": fake_user_password,
        },
    )
    data, error = unwrap_envelope(await response.json())
    assert response.status == 200, (data, error)

    user = await db.get_user({"email": fake_user_email})
    assert user["status"] == UserStatus.CONFIRMATION_PENDING.name

    assert "verification link" in data["message"]

    # retrieves sent link by email (see monkeypatch of email in conftest.py)
    out, _ = capsys.readouterr()
    confirmation_url = parse_link(out)
    assert "/auth/confirmation/" in str(confirmation_url)
    response = await client.get(confirmation_url)
    text = await response.text()

    assert (
        "This is a result of disable_static_webserver fixture for product OSPARC"
        in text
    )
    assert response.status == 200

    # user is active
    user = await db.get_user({"email": fake_user_email})
    assert user["status"] == UserStatus.ACTIVE.name


@pytest.mark.parametrize(
    "is_invitation_required,has_valid_invitation,expected_response",
    [
        (True, True, status.HTTP_200_OK),
        (True, False, status.HTTP_403_FORBIDDEN),
        (False, True, status.HTTP_200_OK),
        (False, False, status.HTTP_200_OK),
    ],
)
async def test_registration_with_invitation(
    client: TestClient,
    login_options: LoginOptions,
    db: AsyncpgStorage,
    is_invitation_required: bool,
    has_valid_invitation: bool,
    expected_response: HTTPStatus,
    mocker: MockerFixture,
    fake_user_email: str,
    fake_user_password: str,
    cleanup_db_tables: None,
):
    assert client.app
    mocker.patch(
        "simcore_service_webserver.login.handlers_registration.get_plugin_settings",
        autospec=True,
        return_value=LoginSettingsForProduct(
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

        url = client.app.router["auth_register"].url_for()

        response = await client.post(
            url.path,
            json={
                "email": fake_user_email,
                "password": fake_user_password,
                "confirm": fake_user_password,
                "invitation": confirmation["code"]
                if has_valid_invitation
                else "WRONG_CODE",
            },
        )
        await assert_status(response, expected_response)

        # check optional fields in body
        if not has_valid_invitation and not is_invitation_required:
            response = await client.post(
                url.path,
                json={
                    "email": "new-user" + fake_user_email,
                    "password": fake_user_password,
                },
            )
            await assert_status(response, expected_response)

        if is_invitation_required and has_valid_invitation:
            assert not await db.get_confirmation(confirmation)


async def test_registraton_with_invitation_for_trial_account(
    client: TestClient,
    login_options: LoginOptions,
    faker: Faker,
    mocker: MockerFixture,
    fake_user_email: str,
    fake_user_password: str,
    cleanup_db_tables: None,
):
    assert client.app
    mocker.patch(
        "simcore_service_webserver.login.handlers_registration.get_plugin_settings",
        autospec=True,
        return_value=LoginSettingsForProduct(
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

        # (3) use register using the invitation code
        url = client.app.router["auth_register"].url_for()
        response = await client.post(
            url.path,
            json={
                "email": fake_user_email,
                "password": fake_user_password,
                "confirm": fake_user_password,
                "invitation": invitation.confirmation["code"],
            },
        )
        await assert_status(response, status.HTTP_200_OK)

        # (4) login
        url = client.app.router["auth_login"].url_for()
        response = await client.post(
            url.path,
            json={
                "email": fake_user_email,
                "password": fake_user_password,
            },
        )
        await assert_status(response, status.HTTP_200_OK)

        # (5) get profile
        url = client.app.router["get_my_profile"].url_for()
        response = await client.get(url.path)
        data, _ = await assert_status(response, status.HTTP_200_OK)
        profile = ProfileGet.model_validate(data)

        expected = invitation.user["created_at"] + timedelta(days=TRIAL_DAYS)
        assert profile.expiration_date
        assert profile.expiration_date == expected.date()
