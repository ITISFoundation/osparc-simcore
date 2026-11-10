# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-statements

import asyncio
import logging
from contextlib import AsyncExitStack
from unittest.mock import AsyncMock

import pytest
import sqlalchemy as sa
from aiohttp.test_utils import TestClient
from faker import Faker
from models_library.authentication import TwoFactorAuthenticationMethod
from models_library.users import UserID
from pytest_mock import MockerFixture, MockType
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.webserver_login import NewInvitation, NewUser
from servicelib.aiohttp import status
from servicelib.utils_secrets import generate_passcode
from settings_library.utils_session import DEFAULT_SESSION_COOKIE_NAME
from simcore_service_webserver.db.models import UserStatus
from simcore_service_webserver.login import _auth_service
from simcore_service_webserver.login._twofa_service import (
    create_2fa_code,
    delete_2fa_code,
    get_redis_validation_code_client,
    has_2fa_code,
    notifications_service,
    send_email_code,
    verify_2fa_code,
)
from simcore_service_webserver.login.constants import (
    CODE_2FA_SMS_CODE_REQUIRED,
    MSG_2FA_UNAVAILABLE,
    MSG_LOGGED_IN,
    MSG_PHONE_REGISTER_2FA_REQUIRED,
    MSG_REGISTRATION_SUCCESS,
    MSG_WRONG_2FA_CODE__INVALID,
)
from simcore_service_webserver.user_preferences import user_preferences_service
from simcore_service_webserver.user_preferences.models import (
    TwoFAFrontendUserPreference,
)
from twilio.base.exceptions import TwilioRestException


@pytest.fixture
def postgres_db(postgres_db_with_2fa_enabled_for_osparc: sa.engine.Engine) -> sa.engine.Engine:
    return postgres_db_with_2fa_enabled_for_osparc


@pytest.fixture
def mocked_twilio_service(mocker: MockerFixture) -> dict[str, MockType]:
    mock = mocker.patch(
        "simcore_service_webserver.login._controller.rest.registration._twofa_service.send_sms_code",
        autospec=True,
    )

    mock_same_submodule = mocker.patch(
        "simcore_service_webserver.login._controller.rest.auth._twofa_service.send_sms_code",
        # NOTE: When importing the full submodule, we are mocking _twofa_service
        #  from .. import _twofa_service
        #  _twofa_service.send_sms_code(...)
        new=mock,
    )

    return {
        "send_sms_code_for_registration": mock,
        "send_sms_code_for_login": mock_same_submodule,
    }


async def test_2fa_code_operations(client: TestClient):
    assert client.app

    # check/verify an entry that does not exist
    assert await has_2fa_code(client.app, "invalid@bar.com") is False
    assert await verify_2fa_code(client.app, user_email="invalid@bar.com", code="123456") is False
    await delete_2fa_code(client.app, "invalid@bar.com")

    # set/verify/delete
    email = "foo@bar.com"
    code = await create_2fa_code(client.app, user_email=email, expiration_in_seconds=60)

    assert await has_2fa_code(client.app, email) is True
    assert await verify_2fa_code(client.app, user_email=email, code=code) is True
    # a wrong code is rejected
    wrong_code = "000000" if code != "000000" else "111111"
    assert await verify_2fa_code(client.app, user_email=email, code=wrong_code) is False
    # only the HMAC digest is persisted, never the plaintext code
    assert await get_redis_validation_code_client(client.app).get(email) != code

    await delete_2fa_code(client.app, email)
    assert await has_2fa_code(client.app, email) is False

    # expired
    email = "expired@bar.com"
    await create_2fa_code(client.app, user_email=email, expiration_in_seconds=1)
    await asyncio.sleep(1.5)
    assert await has_2fa_code(client.app, email) is False


@pytest.mark.acceptance_test
async def test_workflow_register_and_login_with_2fa(  # noqa: PLR0915
    client: TestClient,
    mocked_notifications_service_send_message_from_template: AsyncMock,
    user_email: str,
    user_password: str,
    user_phone_number: str,
    mocked_twilio_service: dict[str, MockType],
    cleanup_db_tables: None,
):
    assert client.app

    # register email+password -----------------------

    # 1. submit: account is created directly and login is granted right away
    # (no e-mail confirmation step)
    # NOTE: since LOGIN_2FA_REQUIRED implies LOGIN_REGISTRATION_INVITATION_REQUIRED
    # (2FA assumes the invitation is what confirms the e-mail), registration
    # here requires a valid invitation code
    async with NewInvitation(client, guest_email=user_email) as invitation:
        assert invitation.confirmation

        url = client.app.router["auth_register"].url_for()
        response = await client.post(
            f"{url}",
            json={
                "email": user_email,
                "password": user_password,
                "confirm": user_password,
                "invitation": invitation.confirmation["code"],
            },
        )
    data, _ = await assert_status(response, status.HTTP_200_OK)
    assert MSG_REGISTRATION_SUCCESS.split(".")[0] in data["message"]

    # registration grants login right away: the response carries the session identity cookie
    assert DEFAULT_SESSION_COOKIE_NAME in response.cookies

    # welcome e-mail is sent
    mocked_notifications_service_send_message_from_template.assert_called_once()
    call_kwargs = mocked_notifications_service_send_message_from_template.call_args.kwargs
    assert call_kwargs["template_name"] == "registered"
    assert call_kwargs["external_contacts"][0].email == user_email
    mocked_notifications_service_send_message_from_template.reset_mock()

    # check email+password registered
    user = await _auth_service.get_user_or_none(client.app, email=user_email)
    assert user
    assert user["status"] == UserStatus.ACTIVE.name
    assert user["phone"] is None

    # 0. login first: still required to grant session access to the 2FA phone
    # registration step (independent from the login cookie set above)
    url = client.app.router["auth_login"].url_for()
    response = await client.post(
        f"{url}",
        json={
            "email": user_email,
            "password": user_password,
        },
    )
    data, _ = await assert_status(response, status.HTTP_202_ACCEPTED)

    # register phone --------------------------------------------------
    # 1. submit
    url = client.app.router["auth_register_phone"].url_for()
    response = await client.post(
        f"{url}",
        json={
            "email": user_email,
            "phone": user_phone_number,
        },
    )
    await assert_status(response, status.HTTP_202_ACCEPTED)

    # check code generated and SMS sent
    assert mocked_twilio_service["send_sms_code_for_registration"].called
    kwargs = mocked_twilio_service["send_sms_code_for_registration"].call_args.kwargs
    phone, received_code = kwargs["phone_number"], kwargs["code"]
    assert phone == user_phone_number

    # check phone still NOT in db (TODO: should be in database and unconfirmed)
    user = await _auth_service.get_user_or_none(client.app, email=user_email)
    assert user
    assert user["status"] == UserStatus.ACTIVE.name
    assert user["phone"] is None

    # 2. confirmation
    url = client.app.router["auth_phone_confirmation"].url_for()
    response = await client.post(
        f"{url}",
        json={
            "email": user_email,
            "phone": user_phone_number,
            "code": received_code,
        },
    )
    await assert_status(response, status.HTTP_200_OK)
    # check user has phone confirmed
    user = await _auth_service.get_user_or_none(client.app, email=user_email)
    assert user
    assert user["status"] == UserStatus.ACTIVE.name
    assert user["phone"] == user_phone_number

    # login (via SMS) ---------------------------------------------------------

    # 1. check email/password then send SMS
    url = client.app.router["auth_login"].url_for()
    response = await client.post(
        f"{url}",
        json={
            "email": user_email,
            "password": user_password,
        },
    )
    data, _ = await assert_status(response, status.HTTP_202_ACCEPTED)

    assert data["name"] == "SMS_CODE_REQUIRED"
    assert data["parameters"]
    assert data["parameters"]["message"]
    assert data["parameters"]["expiration_2fa"]

    # assert SMS was sent
    kwargs = mocked_twilio_service["send_sms_code_for_login"].call_args.kwargs
    phone, received_code = kwargs["phone_number"], kwargs["code"]
    assert phone == user_phone_number

    # 2. check SMS code
    url = client.app.router["auth_login_2fa"].url_for()
    response = await client.post(
        f"{url}",
        json={
            "email": user_email,
            "code": received_code,
        },
    )
    # WARNING: while debugging, breakpoints can add too much delay
    # and make 2fa TTL expire resulting in this validation fail
    await assert_status(response, status.HTTP_200_OK)

    # assert users is successfully registered
    user = await _auth_service.get_user_or_none(client.app, email=user_email)
    assert user
    assert user["email"] == user_email
    assert user["phone"] == user_phone_number
    assert user["status"] == UserStatus.ACTIVE.value

    # login (via EMAIL) ---------------------------------------------------------
    # Change 2fa user preference
    _preference_id = TwoFAFrontendUserPreference().preference_identifier
    await user_preferences_service.set_frontend_user_preference(
        client.app,
        user_id=user["id"],
        product_name="osparc",
        frontend_preference_identifier=_preference_id,
        value=TwoFactorAuthenticationMethod.EMAIL,
    )

    url = client.app.router["auth_login"].url_for()
    response = await client.post(
        f"{url}",
        json={
            "email": user_email,
            "password": user_password,
        },
    )
    data, _ = await assert_status(response, status.HTTP_202_ACCEPTED)

    assert data["name"] == "EMAIL_CODE_REQUIRED"
    assert data["parameters"]
    assert data["parameters"]["message"]
    assert data["parameters"]["expiration_2fa"]

    # assert email was sent via notifications service
    email_call = mocked_notifications_service_send_message_from_template.call_args_list[-1]
    email_context = email_call.kwargs["context"]
    assert email_context["user"]["first_name"] == (user["first_name"] or user["name"])
    assert email_context["user"]["user_name"] == user["name"]

    # login (2FA Disabled) ---------------------------------------------------------
    await user_preferences_service.set_frontend_user_preference(
        client.app,
        user_id=user["id"],
        product_name="osparc",
        frontend_preference_identifier=_preference_id,
        value=TwoFactorAuthenticationMethod.DISABLED,
    )

    url = client.app.router["auth_login"].url_for()
    response = await client.post(
        f"{url}",
        json={
            "email": user_email,
            "password": user_password,
        },
    )
    data, _ = await assert_status(response, status.HTTP_200_OK)
    assert MSG_LOGGED_IN in data["message"]


async def test_can_register_same_phone_in_different_accounts(
    client: TestClient,
    user_email: str,
    user_password: str,
    user_phone_number: str,
    mocked_twilio_service: dict[str, MockType],
    cleanup_db_tables: None,
):
    """
    - Changed policy about user phone constraint in  https://github.com/ITISFoundation/osparc-simcore/pull/5460
    - Tests https://github.com/ITISFoundation/osparc-simcore/issues/3304
    """
    assert client.app

    async with AsyncExitStack() as users_stack:
        # some user ALREADY registered with the same phone
        await users_stack.enter_async_context(NewUser(user_data={"phone": user_phone_number}, app=client.app))

        # some registered user w/o phone
        await users_stack.enter_async_context(
            NewUser(
                user_data={
                    "email": user_email,
                    "password": user_password,
                    "phone": None,
                },
                app=client.app,
            )
        )

        # 1. login
        url = client.app.router["auth_login"].url_for()
        response = await client.post(
            f"{url}",
            json={
                "email": user_email,
                "password": user_password,
            },
        )
        await assert_status(response, status.HTTP_202_ACCEPTED)

        # 2. register existing phone
        url = client.app.router["auth_register_phone"].url_for()
        response = await client.post(
            f"{url}",
            json={
                "email": user_email,
                "phone": user_phone_number,
            },
        )
        data, error = await assert_status(response, status.HTTP_202_ACCEPTED)
        assert data
        assert "SMS" in data["message"]
        assert data["name"] == CODE_2FA_SMS_CODE_REQUIRED
        assert not error


async def test_send_email_code(
    client: TestClient,
    faker: Faker,
    mocker: MockerFixture,
):
    mock_send = mocker.patch(
        f"{notifications_service.__name__}.send_message_from_template",
        autospec=True,
    )

    user_email = faker.email()
    code = generate_passcode()
    first_name = faker.first_name()
    user_name = faker.user_name()

    assert client.app
    await send_email_code(
        client.app,
        user_email=user_email,
        code=code,
        first_name=first_name,
        user_name=user_name,
        product_name="osparc",
        host="osparc.io",
        ttl=120,
    )

    mock_send.assert_called_once()
    call_kwargs = mock_send.call_args.kwargs
    assert call_kwargs["template_name"] == "new_2fa_code"
    assert call_kwargs["context"]["code"] == code
    assert call_kwargs["context"]["host"] == "osparc.io"
    assert call_kwargs["context"]["ttl"] == 120
    assert call_kwargs["context"]["user"]["first_name"] == first_name
    assert call_kwargs["context"]["user"]["user_name"] == user_name


async def test_2fa_sms_failure_during_login(
    client: TestClient,
    user_email: str,
    user_password: str,
    user_phone_number: str,
    caplog: pytest.LogCaptureFixture,
    mocker: MockerFixture,
    cleanup_db_tables: None,
):
    assert client.app

    mocker.patch(
        # MD: Emulates error in graylog https://monitoring.osparc.io/graylog/search/649e7619ce6e0838a96e9bf1?q=%222FA%22&rangetype=relative&from=172800
        "simcore_service_webserver.login._twofa_service.twilio.rest.Client",
        autospec=True,
        side_effect=TwilioRestException(
            status=400,
            uri="https://www.twilio.com/doc",
            msg="Unable to create record: A 'From' phone number is required",
        ),
    )

    # A registered user ...
    async with NewUser(
        user_data={
            "email": user_email,
            "password": user_password,
            "phone": user_phone_number,
        },
        app=client.app,
    ):
        # ... logs in, but fails to send SMS !
        with caplog.at_level(logging.ERROR):
            url = client.app.router["auth_login"].url_for()
            response = await client.post(
                f"{url}",
                json={
                    "email": user_email,
                    "password": user_password,
                },
            )

            # Expects failure:
            #    HTTPServiceUnavailable: Currently we cannot use 2FA, please try again later (OEC:140558738809344)
            data, error = await assert_status(response, status.HTTP_503_SERVICE_UNAVAILABLE)
            assert not data
            assert error["message"].startswith(MSG_2FA_UNAVAILABLE[:10])

            # Expects logs like 'Failed while setting up 2FA code and sending SMS to 157XXXXXXXX3 [OEC:140392495277888]'
            assert f"{user_phone_number[:3]}" in caplog.text


async def test_phone_reconfirmation_cannot_take_over_another_account(
    client: TestClient,
    mocked_twilio_service: dict[str, MockType],
):
    """A fully authenticated session naming another account's email acts on
    its own account only
    """
    assert client.app

    first_phone = "+41770000001"
    second_phone = "+41770000002"
    new_phone = "+41770000003"

    async with AsyncExitStack() as stack:
        first_account = await stack.enter_async_context(NewUser(user_data={"phone": first_phone}, app=client.app))
        second_account = await stack.enter_async_context(NewUser(user_data={"phone": second_phone}, app=client.app))

        # the first account completes a full 2FA login
        response = await client.post(
            f"{client.app.router['auth_login'].url_for()}",
            json={"email": first_account["email"], "password": first_account["raw_password"]},
        )
        await assert_status(response, status.HTTP_202_ACCEPTED)
        code = mocked_twilio_service["send_sms_code_for_login"].call_args.kwargs["code"]
        response = await client.post(
            f"{client.app.router['auth_login_2fa'].url_for()}",
            json={"email": first_account["email"], "code": code},
        )
        await assert_status(response, status.HTTP_200_OK)

        # the flow is submitted naming the second account's email
        response = await client.post(
            f"{client.app.router['auth_register_phone'].url_for()}",
            json={"email": second_account["email"], "phone": new_phone},
        )
        await assert_status(response, status.HTTP_202_ACCEPTED)

        # the OTP was minted for the session's own account, not for the named email
        registration_code = mocked_twilio_service["send_sms_code_for_registration"].call_args.kwargs["code"]
        assert await has_2fa_code(client.app, second_account["email"]) is False
        assert await verify_2fa_code(client.app, user_email=first_account["email"], code=registration_code) is True

        response = await client.post(
            f"{client.app.router['auth_phone_confirmation'].url_for()}",
            json={"email": second_account["email"], "phone": new_phone, "code": registration_code},
        )
        await assert_status(response, status.HTTP_200_OK)

        # the second account is untouched; only the first account's phone changed
        got_second = await _auth_service.get_user_or_none(client.app, email=second_account["email"])
        assert got_second is not None
        assert got_second["phone"] == second_phone

        got_first = await _auth_service.get_user_or_none(client.app, email=first_account["email"])
        assert got_first is not None
        assert got_first["phone"] == new_phone


async def test_phone_reconfirmation_of_account_with_phone_requires_second_factor(
    client: TestClient,
    mocked_twilio_service: dict[str, MockType],
):
    """A password-only login cannot re-point the phone number of an account
    that already has one
    """
    assert client.app

    new_phone = "+41770000009"
    registered_phone = "+41770000010"

    async with AsyncExitStack() as stack:
        first_account = await stack.enter_async_context(NewUser(user_data={"phone": registered_phone}, app=client.app))

        # password-only login: 2FA is pending, the session has no identity
        response = await client.post(
            f"{client.app.router['auth_login'].url_for()}",
            json={"email": first_account["email"], "password": first_account["raw_password"]},
        )
        await assert_status(response, status.HTTP_202_ACCEPTED)

        # trying to replace the EXISTING phone without the second factor
        response = await client.post(
            f"{client.app.router['auth_register_phone'].url_for()}",
            json={"email": first_account["email"], "phone": new_phone},
        )
        _, error = await assert_status(response, status.HTTP_401_UNAUTHORIZED)
        assert error is not None
        assert MSG_PHONE_REGISTER_2FA_REQUIRED.split(".")[0] in error["message"]

        # no SMS went to the new phone and the account's phone is untouched
        sms_calls = mocked_twilio_service["send_sms_code_for_registration"].call_args_list
        assert all(c.kwargs["phone_number"] != new_phone for c in sms_calls)

        got_account = await _auth_service.get_user_or_none(client.app, email=first_account["email"])
        assert got_account is not None
        assert got_account["phone"] == registered_phone


async def test_email_2fa_login_cannot_switch_code_delivery_to_new_phone(
    client: TestClient,
    mocked_notifications_service_send_message_from_template: AsyncMock,
    mocked_twilio_service: dict[str, MockType],
):
    """A password-only login must not deliver the second factor to a phone
    taken from the request through the phone-registration endpoint
    """
    assert client.app

    new_phone = "+41770000021"

    async with AsyncExitStack() as stack:
        first_account = await stack.enter_async_context(NewUser(user_data={}, app=client.app))
        # the account uses the email method and has no phone number registered
        await user_preferences_service.set_frontend_user_preference(
            client.app,
            user_id=UserID(first_account["id"]),
            product_name="osparc",
            frontend_preference_identifier=TwoFAFrontendUserPreference().preference_identifier,
            value=TwoFactorAuthenticationMethod.EMAIL,
        )

        # password-only login: the email code goes to the account's inbox
        response = await client.post(
            f"{client.app.router['auth_login'].url_for()}",
            json={"email": first_account["email"], "password": first_account["raw_password"]},
        )
        await assert_status(response, status.HTTP_202_ACCEPTED)

        # trying to receive the code by SMS on a new phone instead
        response = await client.post(
            f"{client.app.router['auth_register_phone'].url_for()}",
            json={"email": first_account["email"], "phone": new_phone},
        )
        _, error = await assert_status(response, status.HTTP_401_UNAUTHORIZED)
        assert error is not None
        assert MSG_PHONE_REGISTER_2FA_REQUIRED.split(".")[0] in error["message"]

        # no SMS went to the new phone and no phone was registered
        sms_calls = mocked_twilio_service["send_sms_code_for_registration"].call_args_list
        assert all(c.kwargs["phone_number"] != new_phone for c in sms_calls)

        got_account = await _auth_service.get_user_or_none(client.app, email=first_account["email"])
        assert got_account is not None
        assert got_account["phone"] is None


async def test_email_2fa_login_completes_with_email_code(
    client: TestClient,
    mocked_notifications_service_send_message_from_template: AsyncMock,
):
    """The session-bound identity does not disturb the regular email-2FA login"""
    assert client.app

    async with AsyncExitStack() as stack:
        user = await stack.enter_async_context(NewUser(user_data={}, app=client.app))
        await user_preferences_service.set_frontend_user_preference(
            client.app,
            user_id=UserID(user["id"]),
            product_name="osparc",
            frontend_preference_identifier=TwoFAFrontendUserPreference().preference_identifier,
            value=TwoFactorAuthenticationMethod.EMAIL,
        )

        response = await client.post(
            f"{client.app.router['auth_login'].url_for()}",
            json={"email": user["email"], "password": user["raw_password"]},
        )
        data, _ = await assert_status(response, status.HTTP_202_ACCEPTED)
        assert data["name"] == "EMAIL_CODE_REQUIRED"

        email_call = mocked_notifications_service_send_message_from_template.call_args_list[-1]
        assert email_call.kwargs["template_name"] == "new_2fa_code"
        code = email_call.kwargs["context"]["code"]

        response = await client.post(
            f"{client.app.router['auth_login_2fa'].url_for()}",
            json={"email": user["email"], "code": code},
        )
        data, _ = await assert_status(response, status.HTTP_200_OK)
        assert MSG_LOGGED_IN in data["message"]


async def test_resend_2fa_code_uses_session_email_not_body(
    client: TestClient,
    mocked_twilio_service: dict[str, MockType],
):
    """The code resend acts on the account of this session (its pending login),
    not on the email taken from the request body
    """
    assert client.app

    first_phone = "+41770000031"
    second_phone = "+41770000032"

    async with AsyncExitStack() as stack:
        first_account = await stack.enter_async_context(NewUser(user_data={"phone": first_phone}, app=client.app))
        second_account = await stack.enter_async_context(NewUser(user_data={"phone": second_phone}, app=client.app))

        # the first account starts a login: 2FA is pending and grants the resend step
        response = await client.post(
            f"{client.app.router['auth_login'].url_for()}",
            json={"email": first_account["email"], "password": first_account["raw_password"]},
        )
        await assert_status(response, status.HTTP_202_ACCEPTED)

        # resend naming the second account's email
        response = await client.post(
            f"{client.app.router['auth_resend_2fa_code'].url_for()}",
            json={"email": second_account["email"], "via": "SMS"},
        )
        await assert_status(response, status.HTTP_200_OK)

        # the new code was sent to the session's own account and no code exists
        # for the named email
        last_sms = mocked_twilio_service["send_sms_code_for_login"].call_args
        assert last_sms.kwargs["phone_number"] == first_phone
        assert await has_2fa_code(client.app, second_account["email"]) is False
        assert (
            await verify_2fa_code(client.app, user_email=first_account["email"], code=last_sms.kwargs["code"]) is True
        )


async def test_login_continuation_in_authenticated_session_acts_on_pending_login(
    client: TestClient,
    mocked_twilio_service: dict[str, MockType],
):
    """A second login started in a session already authenticated with another
    account completes against the account whose login is pending
    """
    assert client.app

    first_phone = "+41770000041"
    second_phone = "+41770000042"

    async with AsyncExitStack() as stack:
        first_account = await stack.enter_async_context(NewUser(user_data={"phone": first_phone}, app=client.app))
        second_account = await stack.enter_async_context(NewUser(user_data={"phone": second_phone}, app=client.app))

        # the first account completes a full 2FA login: the session holds its identity
        response = await client.post(
            f"{client.app.router['auth_login'].url_for()}",
            json={"email": first_account["email"], "password": first_account["raw_password"]},
        )
        await assert_status(response, status.HTTP_202_ACCEPTED)
        code = mocked_twilio_service["send_sms_code_for_login"].call_args.kwargs["code"]
        response = await client.post(
            f"{client.app.router['auth_login_2fa'].url_for()}",
            json={"email": first_account["email"], "code": code},
        )
        await assert_status(response, status.HTTP_200_OK)

        # the same session starts a login for the second account
        response = await client.post(
            f"{client.app.router['auth_login'].url_for()}",
            json={"email": second_account["email"], "password": second_account["raw_password"]},
        )
        await assert_status(response, status.HTTP_202_ACCEPTED)
        second_code = mocked_twilio_service["send_sms_code_for_login"].call_args.kwargs["code"]

        # the continuation belongs to the pending login, not to the session's
        # existing identity
        response = await client.post(
            f"{client.app.router['auth_login_2fa'].url_for()}",
            json={"email": second_account["email"], "code": second_code},
        )
        data, _ = await assert_status(response, status.HTTP_200_OK)
        assert MSG_LOGGED_IN in data["message"]

        # the second account's code was consumed by the login
        assert await has_2fa_code(client.app, second_account["email"]) is False


async def test_successful_login_clears_an_abandoned_pending_login(
    client: TestClient,
    mocked_twilio_service: dict[str, MockType],
):
    """A successful login that skips 2FA clears the pending email left behind by
    an abandoned login attempt, so the session keeps acting on its own account
    """
    assert client.app

    first_phone = "+41770000051"
    second_phone = "+41770000052"

    async with AsyncExitStack() as stack:
        first_account = await stack.enter_async_context(NewUser(user_data={"phone": first_phone}, app=client.app))
        second_account = await stack.enter_async_context(
            NewUser(user_data={"role": "TESTER", "phone": second_phone}, app=client.app)
        )

        # the first account starts a login that is abandoned at the 2FA step
        response = await client.post(
            f"{client.app.router['auth_login'].url_for()}",
            json={"email": first_account["email"], "password": first_account["raw_password"]},
        )
        await assert_status(response, status.HTTP_202_ACCEPTED)

        # the second account signs in through the 2FA-skipping path (TESTER role)
        response = await client.post(
            f"{client.app.router['auth_login'].url_for()}",
            json={"email": second_account["email"], "password": second_account["raw_password"]},
        )
        data, _ = await assert_status(response, status.HTTP_200_OK)
        assert MSG_LOGGED_IN in data["message"]

        # resend acts on the signed-in account, not on the abandoned pending login
        response = await client.post(
            f"{client.app.router['auth_resend_2fa_code'].url_for()}",
            json={"email": second_account["email"], "via": "SMS"},
        )
        await assert_status(response, status.HTTP_200_OK)

        last_sms = mocked_twilio_service["send_sms_code_for_login"].call_args
        assert last_sms.kwargs["phone_number"] == second_phone


async def test_login_2fa_ignores_a_code_valid_for_another_account(
    client: TestClient,
    mocked_twilio_service: dict[str, MockType],
    mocker: MockerFixture,
):
    """A code valid for another account does not log that account in: the
    endpoint verifies against the session's pending login, not the body email
    """
    assert client.app

    first_phone = "+41770000061"
    second_phone = "+41770000062"

    async with AsyncExitStack() as stack:
        first_account = await stack.enter_async_context(NewUser(user_data={"phone": first_phone}, app=client.app))
        second_account = await stack.enter_async_context(NewUser(user_data={"phone": second_phone}, app=client.app))

        # the first account starts a login: its 2FA is pending in this session
        response = await client.post(
            f"{client.app.router['auth_login'].url_for()}",
            json={"email": first_account["email"], "password": first_account["raw_password"]},
        )
        await assert_status(response, status.HTTP_202_ACCEPTED)
        first_code = mocked_twilio_service["send_sms_code_for_login"].call_args.kwargs["code"]

        # a code valid for the second account, minted outside this session with
        # a fixed value: a random one could equal first_code, and then
        # verifying it against the pending login would legitimately succeed
        second_code = "000000" if first_code != "000000" else "111111"
        mocker.patch(
            "simcore_service_webserver.login._twofa_service.generate_passcode",
            return_value=second_code,
        )
        await create_2fa_code(client.app, user_email=second_account["email"], expiration_in_seconds=60)

        # submitting it under the second account's email does not log that
        # account in
        response = await client.post(
            f"{client.app.router['auth_login_2fa'].url_for()}",
            json={"email": second_account["email"], "code": second_code},
        )
        _, error = await assert_status(response, status.HTTP_401_UNAUTHORIZED)
        assert error is not None
        assert MSG_WRONG_2FA_CODE__INVALID.split(".")[0] in error["message"]

        # the second account's code was neither consumed nor replaced
        assert await verify_2fa_code(client.app, user_email=second_account["email"], code=second_code) is True

        # the session's own login is intact and completes with its own code
        response = await client.post(
            f"{client.app.router['auth_login_2fa'].url_for()}",
            json={"email": first_account["email"], "code": first_code},
        )
        data, _ = await assert_status(response, status.HTTP_200_OK)
        assert MSG_LOGGED_IN in data["message"]
