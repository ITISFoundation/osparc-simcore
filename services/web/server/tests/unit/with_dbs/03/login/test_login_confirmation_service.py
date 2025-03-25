from aiohttp.test_utils import make_mocked_request
from aiohttp.web import Application
from models_library.users import UserID
from simcore_service_webserver.login._confirmation_service import (
    get_or_create_confirmation_without_data,
    is_confirmation_expired,
    make_confirmation_link,
    validate_confirmation_code,
)
from simcore_service_webserver.login._login_repository_legacy import AsyncpgStorage
from simcore_service_webserver.login.settings import LoginOptions


async def test_confirmation_token_workflow(
    db: AsyncpgStorage, login_options: LoginOptions, user_id: UserID
):
    # Step 1: Create a new confirmation token
    action = "RESET_PASSWORD"
    confirmation = await get_or_create_confirmation_without_data(
        login_options, db, user_id=user_id, action=action
    )

    assert confirmation is not None
    assert confirmation["user_id"] == user_id
    assert confirmation["action"] == action

    # Step 2: Check that the token is not expired
    assert not is_confirmation_expired(login_options, confirmation)

    # Step 3: Validate the confirmation code
    code = confirmation["code"]
    validated_confirmation = await validate_confirmation_code(code, db, login_options)

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
        "GET", "/auth/confirmation/{code}", app=app, headers={"Host": "example.com"}
    )
    request.scheme = "http"

    # Create confirmation link
    confirmation_link = make_confirmation_link(request, confirmation)

    # Assertions
    assert confirmation_link.startswith("http://example.com/auth/confirmation/")
    assert confirmation["code"] in confirmation_link
