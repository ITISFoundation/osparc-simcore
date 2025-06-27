from datetime import timedelta

from aiohttp.test_utils import make_mocked_request
from aiohttp.web import Application
from pytest_simcore.helpers.webserver_users import UserInfoDict
from simcore_service_webserver.login import _confirmation_service, _confirmation_web
from simcore_service_webserver.login._login_repository_legacy import AsyncpgStorage
from simcore_service_webserver.login.settings import LoginOptions


async def test_confirmation_token_workflow(
    db: AsyncpgStorage, login_options: LoginOptions, registered_user: UserInfoDict
):
    # Step 1: Create a new confirmation token
    user_id = registered_user["id"]
    action = "RESET_PASSWORD"
    confirmation = await _confirmation_service.get_or_create_confirmation_without_data(
        login_options, db, user_id=user_id, action=action
    )

    assert confirmation is not None
    assert confirmation["user_id"] == user_id
    assert confirmation["action"] == action

    # Step 2: Check that the token is not expired
    assert not _confirmation_service.is_confirmation_expired(
        login_options, confirmation
    )

    # Step 3: Validate the confirmation code
    code = confirmation["code"]
    validated_confirmation = await _confirmation_service.validate_confirmation_code(
        code, db, login_options
    )

    assert validated_confirmation is not None
    assert validated_confirmation["code"] == code
    assert validated_confirmation["user_id"] == user_id
    assert validated_confirmation["action"] == action

    # Step 4: Create confirmation link
    app = Application()
    app.router.add_get(
        "/auth/confirmation/{code}", lambda request: None, name="auth_confirmation"
    )
    request = make_mocked_request(
        "GET",
        "https://example.com/auth/confirmation/{code}",
        app=app,
        headers={"Host": "example.com"},
    )

    # Create confirmation link
    confirmation_link = _confirmation_web.make_confirmation_link(
        request, confirmation["code"]
    )

    # Assertions
    assert confirmation_link.startswith("https://example.com/auth/confirmation/")
    assert confirmation["code"] in confirmation_link


async def test_expired_confirmation_token(
    db: AsyncpgStorage, login_options: LoginOptions, registered_user: UserInfoDict
):
    user_id = registered_user["id"]
    action = "CHANGE_EMAIL"

    # Create a brand new confirmation token
    confirmation_1 = (
        await _confirmation_service.get_or_create_confirmation_without_data(
            login_options, db, user_id=user_id, action=action
        )
    )

    assert confirmation_1 is not None
    assert confirmation_1["user_id"] == user_id
    assert confirmation_1["action"] == action

    # Check that the token is not expired
    assert not _confirmation_service.is_confirmation_expired(
        login_options, confirmation_1
    )
    assert _confirmation_service.get_expiration_date(login_options, confirmation_1)

    confirmation_2 = (
        await _confirmation_service.get_or_create_confirmation_without_data(
            login_options, db, user_id=user_id, action=action
        )
    )

    assert confirmation_2 == confirmation_1

    # Enforce ALL EXPIRED
    login_options.CHANGE_EMAIL_CONFIRMATION_LIFETIME = 0
    assert login_options.get_confirmation_lifetime(action) == timedelta(seconds=0)

    confirmation_3 = (
        await _confirmation_service.get_or_create_confirmation_without_data(
            login_options, db, user_id=user_id, action=action
        )
    )

    # when expired, it gets renewed
    assert confirmation_3 != confirmation_1

    # now all have expired
    assert (
        await _confirmation_service.validate_confirmation_code(
            confirmation_1["code"], db, login_options
        )
        is None
    )
    assert (
        await _confirmation_service.validate_confirmation_code(
            confirmation_2["code"], db, login_options
        )
        is None
    )
    assert (
        await _confirmation_service.validate_confirmation_code(
            confirmation_3["code"], db, login_options
        )
        is None
    )
