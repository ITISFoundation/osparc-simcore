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
from models_library.products import ProductName
from pytest_simcore.helpers.webserver_users import UserInfoDict
from servicelib.aiohttp import status
from simcore_service_webserver.login._login_repository_legacy import (
    ActionLiteralStr,
    AsyncpgStorage,
    ConfirmationTokenDict,
)
from simcore_service_webserver.users import _users_service
from simcore_service_webserver.wallets import _api as _wallets_service
from simcore_service_webserver.wallets import _db as _wallets_repository

CreateTokenCallable: TypeAlias = Callable[
    [int, ActionLiteralStr, str | None], Coroutine[Any, Any, ConfirmationTokenDict]
]


@pytest.fixture
async def create_valid_confirmation_token(db: AsyncpgStorage) -> CreateTokenCallable:
    """Fixture to create a valid confirmation token for a given action."""

    async def _create_token(
        user_id: int, action: ActionLiteralStr, data: str | None = None
    ) -> ConfirmationTokenDict:
        return await db.create_confirmation(user_id=user_id, action=action, data=data)

    return _create_token


async def test_confirm_registration(
    client: TestClient,
    create_valid_confirmation_token: CreateTokenCallable,
    unconfirmed_user: UserInfoDict,
    product_name: ProductName,
):
    assert unconfirmed_user["status"] == UserStatus.CONFIRMATION_PENDING
    target_user_id = unconfirmed_user["id"]
    confirmation = await create_valid_confirmation_token(
        target_user_id, "REGISTRATION", None
    )
    code = confirmation["code"]

    # clicks link to confirm registration
    response = await client.get(f"/v0/auth/confirmation/{code}")
    assert response.status == status.HTTP_200_OK

    # checks redirection
    assert len(response.history) == 1
    assert response.history[0].status == status.HTTP_302_FOUND
    assert response.history[0].headers["Location"].endswith("/#?registered=true")

    # checks _handle_confirm_registration updated status
    assert client.app
    user = await _users_service.get_user(client.app, user_id=unconfirmed_user["id"])
    assert user["status"] == UserStatus.ACTIVE

    # checks that the user has one wallet created (via SIGNAL_ON_USER_CONFIRMATION)
    wallets = await _wallets_service.list_wallets_for_user(
        client.app, user_id=unconfirmed_user["id"], product_name=product_name
    )
    assert len(wallets) == 1

    # delete to allow teardown
    await _wallets_repository.delete_wallet(
        client.app,
        wallet_id=wallets[0].wallet_id,
        product_name=product_name,
    )


async def test_confirm_change_email(
    client: TestClient,
    create_valid_confirmation_token: CreateTokenCallable,
    registered_user: UserInfoDict,
):
    assert registered_user["status"] == UserStatus.ACTIVE

    user_id = registered_user["id"]
    confirmation = await create_valid_confirmation_token(
        user_id, "CHANGE_EMAIL", "new_" + registered_user["email"]
    )
    code = confirmation["code"]

    # clicks link to confirm registration
    response = await client.get(f"/v0/auth/confirmation/{code}")
    assert response.status == status.HTTP_200_OK

    # checks _handle_confirm_registration updated status
    assert client.app
    user = await _users_service.get_user(client.app, user_id=registered_user["id"])
    assert user["email"] == "new_" + registered_user["email"]


async def test_confirm_reset_password(
    client: TestClient,
    create_valid_confirmation_token: CreateTokenCallable,
    registered_user: UserInfoDict,
):
    user_id = registered_user["id"]
    confirmation = await create_valid_confirmation_token(
        user_id, "RESET_PASSWORD", None
    )
    code = confirmation["code"]

    response = await client.get(f"/v0/auth/confirmation/{code}")
    assert response.status == status.HTTP_200_OK

    # checks redirection
    assert len(response.history) == 1
    assert response.history[0].status == status.HTTP_302_FOUND
    assert (
        response.history[0]
        .headers["Location"]
        .endswith(f"/#reset-password?code={code}")
    )


async def test_handler_exception_logging(
    client: TestClient,
    create_valid_confirmation_token: CreateTokenCallable,
    registered_user: UserInfoDict,
):
    user_id = registered_user["id"]
    confirmation = await create_valid_confirmation_token(user_id, "REGISTRATION", None)
    code = confirmation["code"]

    with patch(
        "simcore_service_webserver.login._controller.rest.confirmation._handle_confirm_registration",
        new_callable=AsyncMock,
        side_effect=Exception("Test exception"),
    ) as mock_handler, patch(
        "simcore_service_webserver.login._controller.rest.confirmation._logger.exception"
    ) as mock_logger:
        response = await client.get(f"/v0/auth/confirmation/{code}")
        assert response.status == status.HTTP_200_OK

        # checks redirection
        assert len(response.history) == 1
        assert response.history[0].status == status.HTTP_302_FOUND
        assert "/#/error?message=" in response.history[0].headers["Location"]

        mock_handler.assert_called_once()
        mock_logger.assert_called_once()
