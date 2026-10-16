# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiohttp import web
from models_library.products import ProductName
from pytest_mock import MockerFixture
from simcore_service_webserver.login import _auth_service, _login_throttle_service
from simcore_service_webserver.login.errors import WrongPasswordError


async def test_unknown_user_is_verified_against_dummy_hash_and_rejected(
    mocker: MockerFixture, product_name: ProductName
):
    mock_check_password = mocker.patch.object(_auth_service.security_service, "check_password", return_value=False)
    product = SimpleNamespace(name=product_name)

    with pytest.raises(WrongPasswordError) as exc_info:
        await _auth_service.check_authorized_user_credentials(
            MagicMock(),
            None,
            password="some-password",  # noqa: S106
            product=product,  # type: ignore[arg-type]
        )

    assert exc_info.value.error_context()["user_id"] is None
    mock_check_password.assert_called_once_with("some-password", _auth_service._get_dummy_password_hash())  # noqa: SLF001
    assert _auth_service._get_dummy_password_hash().startswith("$argon2id$")  # noqa: SLF001


@pytest.fixture
def mock_throttle(mocker: MockerFixture) -> dict[str, AsyncMock]:
    return {
        name: mocker.patch.object(_login_throttle_service, name, new_callable=AsyncMock)
        for name in ("raise_if_login_throttled", "register_failed_login", "clear_failed_logins")
    }


@pytest.fixture
def mock_login_settings(mocker: MockerFixture) -> MagicMock:
    return mocker.patch.object(_auth_service, "get_plugin_settings", return_value=MagicMock())


async def test_authenticate_user_registers_failures_and_reraises(
    mocker: MockerFixture,
    product_name: ProductName,
    mock_throttle: dict[str, AsyncMock],
    mock_login_settings: MagicMock,
):
    mocker.patch.object(_auth_service, "get_user_or_none", return_value=None)
    mocker.patch.object(_auth_service, "check_authorized_user_credentials", side_effect=WrongPasswordError(user_id=1))
    product = SimpleNamespace(name=product_name)

    with pytest.raises(WrongPasswordError):
        await _auth_service.authenticate_user(
            MagicMock(),
            email="a@b.com",
            password="some-password",  # noqa: S106
            product=product,  # type: ignore[arg-type]
        )

    mock_throttle["raise_if_login_throttled"].assert_awaited_once()
    mock_throttle["register_failed_login"].assert_awaited_once()
    mock_throttle["clear_failed_logins"].assert_not_awaited()


async def test_authenticate_user_clears_failures_on_success(
    mocker: MockerFixture,
    product_name: ProductName,
    mock_throttle: dict[str, AsyncMock],
    mock_login_settings: MagicMock,
):
    expected_user = {"id": 1, "email": "a@b.com"}
    mocker.patch.object(_auth_service, "get_user_or_none", return_value=expected_user)
    mocker.patch.object(_auth_service, "check_authorized_user_credentials", return_value=expected_user)
    product = SimpleNamespace(name=product_name)

    user = await _auth_service.authenticate_user(
        MagicMock(),
        email="a@b.com",
        password="some-password",  # noqa: S106
        product=product,  # type: ignore[arg-type]
    )

    assert user == expected_user
    mock_throttle["clear_failed_logins"].assert_awaited_once()
    mock_throttle["register_failed_login"].assert_not_awaited()


async def test_authenticate_user_does_not_check_credentials_while_throttled(
    mocker: MockerFixture,
    product_name: ProductName,
    mock_throttle: dict[str, AsyncMock],
    mock_login_settings: MagicMock,
):
    mock_throttle["raise_if_login_throttled"].side_effect = web.HTTPTooManyRequests()
    mock_get_user = mocker.patch.object(_auth_service, "get_user_or_none")
    mock_check = mocker.patch.object(_auth_service, "check_authorized_user_credentials")
    product = SimpleNamespace(name=product_name)

    with pytest.raises(web.HTTPTooManyRequests):
        await _auth_service.authenticate_user(
            MagicMock(),
            email="a@b.com",
            password="some-password",  # noqa: S106
            product=product,  # type: ignore[arg-type]
        )

    mock_get_user.assert_not_called()
    mock_check.assert_not_called()
    mock_throttle["register_failed_login"].assert_not_awaited()
