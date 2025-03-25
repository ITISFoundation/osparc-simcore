# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

from collections.abc import Callable, Coroutine
from typing import Any, TypeAlias
from unittest.mock import AsyncMock, patch

import pytest
from aiohttp.test_utils import TestClient
from common_library.users_enums import UserStatus
from pytest_simcore.helpers.webserver_login import UserInfoDict
from servicelib.aiohttp import status
from simcore_service_webserver.login._login_repository_legacy import (
    ActionLiteralStr,
    AsyncpgStorage,
    ConfirmationTokenDict,
)

CreateTokenCallable: TypeAlias = Callable[
    [int, ActionLiteralStr], Coroutine[Any, Any, ConfirmationTokenDict]
]


@pytest.fixture
async def create_valid_confirmation_token(db: AsyncpgStorage) -> CreateTokenCallable:
    """Fixture to create a valid confirmation token for a given action."""

    async def _create_token(
        user_id: int, action: ActionLiteralStr
    ) -> ConfirmationTokenDict:
        return await db.create_confirmation(user_id=user_id, action=action)

    return _create_token


async def test_confirm_registration(
    client: TestClient,
    create_valid_confirmation_token: CreateTokenCallable,
    unconfirmed_user: UserInfoDict,
):
    assert unconfirmed_user["status"] == UserStatus.CONFIRMATION_PENDING
    target_user_id = unconfirmed_user["id"]
    confirmation = await create_valid_confirmation_token(target_user_id, "REGISTRATION")
    code = confirmation["code"]

    # consuming code
    response = await client.get(f"/v0/auth/confirmation/{code}")
    assert response.status == status.HTTP_302_FOUND
    assert response.headers["Location"].endswith("?registered=true")


async def test_confirm_change_email(
    client: TestClient,
    create_valid_confirmation_token: CreateTokenCallable,
    registered_user: UserInfoDict,
):
    user_id = registered_user["id"]
    confirmation = await create_valid_confirmation_token(user_id, "CHANGE_EMAIL")
    code = confirmation["code"]

    response = await client.get(f"/v0/auth/confirmation/{code}")
    assert response.status == status.HTTP_302_FOUND
    assert "Location" in response.headers


async def test_confirm_reset_password(
    client: TestClient,
    create_valid_confirmation_token: CreateTokenCallable,
    registered_user: UserInfoDict,
):
    user_id = registered_user["id"]
    confirmation = await create_valid_confirmation_token(user_id, "RESET_PASSWORD")
    code = confirmation["code"]

    response = await client.get(f"/v0/auth/confirmation/{code}")
    assert response.status == status.HTTP_302_FOUND
    assert response.headers["Location"].endswith(f"reset-password?code={code}")


async def test_handler_exception_logging(
    client: TestClient,
    create_valid_confirmation_token: CreateTokenCallable,
    registered_user: UserInfoDict,
):
    user_id = registered_user["id"]
    confirmation = await create_valid_confirmation_token(user_id, "REGISTRATION")
    code = confirmation["code"]

    with patch(
        "simcore_service_webserver.login._controller.confirmation_rest._handle_confirm_registration",
        new_callable=AsyncMock,
        side_effect=Exception("Test exception"),
    ) as mock_handler, patch(
        "simcore_service_webserver.login._controller.confirmation_rest._logger.exception"
    ) as mock_logger:
        response = await client.get(f"/v0/auth/confirmation/{code}")
        assert response.status == 503
        mock_handler.assert_called_once()
        mock_logger.assert_called_once_with(
            user_error_msg="Sorry, we cannot confirm your REGISTRATION."
            "Please try again in a few moments.",
            error=mock_handler.side_effect,
            error_code=mock_handler.side_effect,
            tip="Failed during email_confirmation",
        )
