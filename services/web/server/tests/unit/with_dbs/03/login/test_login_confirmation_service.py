from datetime import timedelta

from aiohttp import web
from aiohttp.test_utils import make_mocked_request
from pytest_simcore.helpers.webserver_users import UserInfoDict
from simcore_service_webserver.login import _confirmation_web
from simcore_service_webserver.login._confirmation_service import ConfirmationService


async def test_confirmation_token_workflow(
    confirmation_service: ConfirmationService,
    registered_user: UserInfoDict,
):
    # Step 1: Create a new confirmation token
    user_id = registered_user["id"]
    action = "RESET_PASSWORD"
    confirmation = await confirmation_service.get_or_create_confirmation_without_data(
        user_id=user_id, action=action
    )

    assert confirmation is not None
    assert confirmation.user_id == user_id
    assert confirmation.action == action

    # Step 2: Check that the token is not expired
    assert not confirmation_service.is_confirmation_expired(confirmation)

    # Step 3: Validate the confirmation code
    code = confirmation.code
    validated_confirmation = await confirmation_service.validate_confirmation_code(code)

    assert validated_confirmation is not None
    assert validated_confirmation.code == code
    assert validated_confirmation.user_id == user_id
    assert validated_confirmation.action == action

    # Step 4: Create confirmation link
    app = web.Application()

    async def mock_handler(request: web.Request):
        assert request.match_info["code"] == confirmation.code
        return web.Response()

    app.router.add_get(
        "/auth/confirmation/{code}", mock_handler, name="auth_confirmation"
    )
    request = make_mocked_request(
        "GET",
        "https://example.com/auth/confirmation/{code}",
        app=app,
        headers={"Host": "example.com"},
    )

    # Create confirmation link
    confirmation_link = _confirmation_web.make_confirmation_link(
        request, confirmation.code
    )

    # Assertions
    assert confirmation_link.startswith("https://example.com/auth/confirmation/")
    assert confirmation.code in confirmation_link


async def test_expired_confirmation_token(
    confirmation_service: ConfirmationService,
    registered_user: UserInfoDict,
):
    user_id = registered_user["id"]
    action = "CHANGE_EMAIL"

    # Create a brand new confirmation token
    confirmation_1 = await confirmation_service.get_or_create_confirmation_without_data(
        user_id=user_id, action=action
    )

    assert confirmation_1 is not None
    assert confirmation_1.user_id == user_id
    assert confirmation_1.action == action

    # Check that the token is not expired
    assert not confirmation_service.is_confirmation_expired(confirmation_1)
    assert confirmation_service.get_expiration_date(confirmation_1)

    confirmation_2 = await confirmation_service.get_or_create_confirmation_without_data(
        user_id=user_id, action=action
    )

    assert confirmation_2 == confirmation_1

    # Enforce ALL EXPIRED
    confirmation_service.options.CHANGE_EMAIL_CONFIRMATION_LIFETIME = 0
    assert confirmation_service.options.get_confirmation_lifetime(action) == timedelta(
        seconds=0
    )

    confirmation_3 = await confirmation_service.get_or_create_confirmation_without_data(
        user_id=user_id, action=action
    )

    # when expired, it gets renewed
    assert confirmation_3 != confirmation_1

    # now all have expired
    assert (
        await confirmation_service.validate_confirmation_code(confirmation_1.code)
        is None
    )
    assert (
        await confirmation_service.validate_confirmation_code(confirmation_2.code)
        is None
    )
    assert (
        await confirmation_service.validate_confirmation_code(confirmation_3.code)
        is None
    )
