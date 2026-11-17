# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import asyncio
from collections.abc import Callable
from datetime import timedelta
from typing import Annotated, Final

import pytest
import sqlalchemy as sa
from aiohttp.test_utils import TestClient
from annotated_types import doc
from pytest_mock import MockFixture
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.webserver_users import NewUser, UserInfoDict
from servicelib.aiohttp import status
from simcore_service_webserver.login._controller.rest.auth_schemas import (
    CodePageParams,
    NextPage,
)
from simcore_service_webserver.login.constants import (
    CODE_2FA_SMS_CODE_REQUIRED,
    CODE_PHONE_NUMBER_REQUIRED,
    MAX_2FA_CODE_TRIALS,
    MSG_LOGGED_IN,
)
from simcore_service_webserver.login.errors import SendingVerificationSmsError
from simcore_service_webserver.login.settings import LOGIN_SETTINGS_PER_PRODUCT_APPKEY

pytest_simcore_core_services_selection = [
    "postgres",
    "redis",
    "rabbit",
]

pytestmark = pytest.mark.usefixtures("clean_2fa_redis_state")

_COOLDOWN_WINDOW: Final[
    Annotated[timedelta, doc("long enough that the repeated-rejection assertions cannot race its expiry")]
] = timedelta(seconds=30)

_SHORT_COOLDOWN: Final[Annotated[timedelta, doc("window the cooldown-expiry test waits out")]] = timedelta(seconds=1)

_SLEEP_PAST_SHORT_COOLDOWN: Final[
    Annotated[float, doc("short cooldown plus the slack of Redis' second-granularity expiry")]
] = _SHORT_COOLDOWN.total_seconds() + 1.2


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

    mock_has_2fa_code = mocker.patch(
        "simcore_service_webserver.login._controller.rest.twofa._twofa_service.has_2fa_code",
        autospec=True,
        return_value=False,  # <-- Emulates code expired
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

    assert mock_has_2fa_code.call_count == 1, "Emulates code expired"
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

    assert mock_has_2fa_code.call_count == 2, "Emulates code expired"
    assert mock_send_email_code.call_count == 1, "Email was not sent??"


@pytest.fixture
def with_2fa_code_resend_cooldown_secs(
    client: TestClient,
) -> Callable[[timedelta], None]:
    """Overrides the per-product resend cooldown on the app settings, where
    both the resend and the register-phone handler read it.

    Tests express the cooldown as a `timedelta` for readability: it is a
    duration, not a bare number. It is converted to seconds here only because
    the setting (`LOGIN_2FA_CODE_RESEND_COOLDOWN_SEC`) is stored as an int
    """

    def _set(cooldown: timedelta) -> None:
        assert client.app
        product_settings = client.app[LOGIN_SETTINGS_PER_PRODUCT_APPKEY]["osparc"]
        client.app[LOGIN_SETTINGS_PER_PRODUCT_APPKEY]["osparc"] = product_settings.model_copy(
            update={"LOGIN_2FA_CODE_RESEND_COOLDOWN_SEC": int(cooldown.total_seconds())}
        )

    return _set


async def _login(client: TestClient, registered_user: UserInfoDict) -> None:
    url = client.app.router["auth_login"].url_for()
    response = await client.post(
        f"{url}",
        json={
            "email": registered_user["email"],
            "password": registered_user["raw_password"],
        },
    )
    await assert_status(response, status.HTTP_202_ACCEPTED)


async def _resend(client: TestClient, registered_user: UserInfoDict, via: str):
    url = client.app.router["auth_resend_2fa_code"].url_for()
    return await client.post(
        f"{url}",
        json={
            "email": registered_user["email"],
            "via": via,
        },
    )


async def test_resend_2fa_cooldown_blocks_repeat_within_window(
    client: TestClient,
    registered_user: UserInfoDict,
    mocker: MockFixture,
    with_2fa_code_resend_cooldown_secs: Callable[[timedelta], None],
):
    """The cooldown between resends is kept server-side per account and
    channel: the server refuses repeats within the window, and repeated
    rejections never exhaust the session's authorization. The window is long
    enough that these assertions cannot race its expiry
    """
    assert client.app

    mocker.patch(
        "simcore_service_webserver.login._twofa_service.send_sms_code",
        autospec=True,
    )
    mocker.patch(
        "simcore_service_webserver.login._twofa_service.send_email_code",
        autospec=True,
    )
    with_2fa_code_resend_cooldown_secs(_COOLDOWN_WINDOW)

    await _login(client, registered_user)

    response = await _resend(client, registered_user, "SMS")
    await assert_status(response, status.HTTP_200_OK)

    response = await _resend(client, registered_user, "SMS")
    assert response.status == status.HTTP_429_TOO_MANY_REQUESTS
    assert (
        int(_COOLDOWN_WINDOW.total_seconds()) - 5
        <= int(response.headers["Retry-After"])
        <= int(_COOLDOWN_WINDOW.total_seconds())
    )

    # a cooldown rejection is not a use of the step: repeated rejections never
    # exhaust the session's authorization, so retrying after Retry-After works
    for _ in range(MAX_2FA_CODE_TRIALS + 1):
        response = await _resend(client, registered_user, "SMS")
        assert response.status == status.HTTP_429_TOO_MANY_REQUESTS

    # the email channel has its own window
    response = await _resend(client, registered_user, "Email")
    await assert_status(response, status.HTTP_200_OK)


async def test_resend_2fa_cooldown_expires_after_the_window(
    client: TestClient,
    registered_user: UserInfoDict,
    mocker: MockFixture,
    with_2fa_code_resend_cooldown_secs: Callable[[timedelta], None],
):
    """Once the window elapsed, resending via the same channel is granted again"""
    assert client.app

    mocker.patch(
        "simcore_service_webserver.login._twofa_service.send_sms_code",
        autospec=True,
    )
    with_2fa_code_resend_cooldown_secs(_SHORT_COOLDOWN)

    await _login(client, registered_user)

    response = await _resend(client, registered_user, "SMS")
    await assert_status(response, status.HTTP_200_OK)

    response = await _resend(client, registered_user, "SMS")
    assert response.status == status.HTTP_429_TOO_MANY_REQUESTS

    await asyncio.sleep(_SLEEP_PAST_SHORT_COOLDOWN)
    response = await _resend(client, registered_user, "SMS")
    await assert_status(response, status.HTTP_200_OK)


async def test_resend_2fa_send_failure_releases_the_cooldown(
    client: TestClient,
    registered_user: UserInfoDict,
    mocker: MockFixture,
    with_2fa_code_resend_cooldown_secs: Callable[[timedelta], None],
):
    """A resend whose delivery failed sent no code: the retry must not be
    charged for a window that delivered nothing
    """
    assert client.app

    mocker.patch(
        "simcore_service_webserver.login._twofa_service.send_email_code",
        autospec=True,
    )
    sms_mock = mocker.patch(
        "simcore_service_webserver.login._twofa_service.send_sms_code",
        autospec=True,
    )
    with_2fa_code_resend_cooldown_secs(_COOLDOWN_WINDOW)

    await _login(client, registered_user)

    sms_mock.side_effect = SendingVerificationSmsError(details="twilio unavailable")
    response = await _resend(client, registered_user, "SMS")
    _, error = await assert_status(response, status.HTTP_503_SERVICE_UNAVAILABLE)
    assert error is not None

    # the failed request released the window it armed, so an immediate retry
    # goes through; the retry arms a new window
    sms_mock.side_effect = None
    response = await _resend(client, registered_user, "SMS")
    await assert_status(response, status.HTTP_200_OK)

    response = await _resend(client, registered_user, "SMS")
    assert response.status == status.HTTP_429_TOO_MANY_REQUESTS


async def test_email_resend_logs_in_an_sms_account_without_phone(
    client: TestClient,
    user_email: str,
    user_password: str,
    mocker: MockFixture,
):
    """An account whose 2FA method is SMS but that has no phone registered
    (users.phone NULL) is sent to the phone-registration page on login; the
    email button is its only way in. The email resend must not require a phone
    number, and the rejected SMS resend must not consume the email window
    """
    assert client.app

    send_email_mock = mocker.patch(
        "simcore_service_webserver.login._twofa_service.send_email_code",
        autospec=True,
    )

    async with NewUser(
        user_data={"email": user_email, "password": user_password, "phone": None},
        app=client.app,
    ) as account:
        # the SMS method without a phone asks to register a phone, no code sent
        response = await client.post(
            f"{client.app.router['auth_login'].url_for()}",
            json={"email": user_email, "password": account["raw_password"]},
        )
        data, _ = await assert_status(response, status.HTTP_202_ACCEPTED)
        assert data["name"] == CODE_PHONE_NUMBER_REQUIRED

        # an SMS resend is rejected before arming any cooldown
        response = await _resend(client, account, "SMS")
        assert response.status == status.HTTP_400_BAD_REQUEST

        # the email button: no phone needed, the SMS rejection cost nothing
        response = await _resend(client, account, "Email")
        await assert_status(response, status.HTTP_200_OK)
        code = send_email_mock.call_args.kwargs["code"]

        response = await client.post(
            f"{client.app.router['auth_login_2fa'].url_for()}",
            json={"email": user_email, "code": code},
        )
        data, _ = await assert_status(response, status.HTTP_200_OK)
        assert MSG_LOGGED_IN in data["message"]
