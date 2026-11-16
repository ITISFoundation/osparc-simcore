# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import contextlib
from ipaddress import ip_address, ip_network
from unittest.mock import AsyncMock, MagicMock

import pytest
from faker import Faker
from pytest_mock import MockerFixture
from simcore_service_webserver.login import _auth_service, _login_throttle_service
from simcore_service_webserver.login.errors import LoginThrottledError, WrongPasswordError
from simcore_service_webserver.login.settings import LoginThrottleSettings
from simcore_service_webserver.products.models import Product


async def test_unknown_user_is_verified_against_dummy_hash_and_rejected(mocker: MockerFixture, product: Product):
    mock_check_password = mocker.patch.object(_auth_service.security_service, "check_password", return_value=False)

    with pytest.raises(WrongPasswordError) as exc_info:
        await _auth_service.check_authorized_user_credentials(
            MagicMock(),
            None,
            password="some-password",  # noqa: S106
            product=product,
        )

    assert exc_info.value.error_context()["user_id"] is None
    mock_check_password.assert_called_once_with("some-password", _auth_service._get_dummy_password_hash())  # noqa: SLF001
    assert _auth_service._get_dummy_password_hash().startswith("$argon2id$")  # noqa: SLF001


@pytest.fixture
def mock_throttle(mocker: MockerFixture) -> dict[str, AsyncMock]:
    mocker.patch.object(
        _login_throttle_service, "exclusive_login_attempt", side_effect=lambda *_, **__: contextlib.nullcontext()
    )
    return {
        name: mocker.patch.object(_login_throttle_service, name, new_callable=AsyncMock)
        for name in ("raise_if_login_throttled", "register_failed_login", "clear_failed_logins")
    }


@pytest.fixture
def mock_login_settings(mocker: MockerFixture) -> MagicMock:
    return mocker.patch.object(_auth_service, "get_plugin_settings", return_value=MagicMock())


async def test_authenticate_user_registers_failures_and_reraises(
    mocker: MockerFixture,
    faker: Faker,
    product: Product,
    mock_throttle: dict[str, AsyncMock],
    mock_login_settings: MagicMock,
):
    mocker.patch.object(_auth_service, "get_user_or_none", return_value=None)
    mocker.patch.object(_auth_service, "check_authorized_user_credentials", side_effect=WrongPasswordError(user_id=1))

    with pytest.raises(WrongPasswordError):
        await _auth_service.authenticate_user(
            MagicMock(),
            email=faker.email(),
            password="wrong-password",  # noqa: S106
            product=product,
        )

    mock_throttle["raise_if_login_throttled"].assert_awaited_once()
    mock_throttle["register_failed_login"].assert_awaited_once()
    mock_throttle["clear_failed_logins"].assert_not_awaited()


async def test_authenticate_user_clears_failures_on_success(
    mocker: MockerFixture,
    faker: Faker,
    product: Product,
    mock_throttle: dict[str, AsyncMock],
    mock_login_settings: MagicMock,
):
    expected_user = {"id": 1, "email": faker.email()}
    mocker.patch.object(_auth_service, "get_user_or_none", return_value=expected_user)
    mocker.patch.object(_auth_service, "check_authorized_user_credentials", return_value=expected_user)

    user = await _auth_service.authenticate_user(
        MagicMock(),
        email=expected_user["email"],
        password="correct-password",  # noqa: S106
        product=product,
    )

    assert user == expected_user
    mock_throttle["clear_failed_logins"].assert_awaited_once()
    mock_throttle["register_failed_login"].assert_not_awaited()


async def test_authenticate_user_does_not_check_credentials_while_throttled(
    mocker: MockerFixture,
    faker: Faker,
    product: Product,
    mock_throttle: dict[str, AsyncMock],
    mock_login_settings: MagicMock,
):
    mock_throttle["raise_if_login_throttled"].side_effect = LoginThrottledError(retry_after_sec=1)
    mock_get_user = mocker.patch.object(_auth_service, "get_user_or_none")
    mock_check = mocker.patch.object(_auth_service, "check_authorized_user_credentials")

    with pytest.raises(LoginThrottledError):
        await _auth_service.authenticate_user(
            MagicMock(),
            email=faker.email(),
            password="irrelevant",  # noqa: S106
            product=product,
        )

    mock_get_user.assert_not_called()
    mock_check.assert_not_called()
    mock_throttle["register_failed_login"].assert_not_awaited()


@pytest.fixture
def mock_trusted_login_settings(mocker: MockerFixture) -> MagicMock:
    return mocker.patch.object(
        _auth_service,
        "get_plugin_settings",
        return_value=MagicMock(
            LOGIN_THROTTLE=LoginThrottleSettings(LOGIN_THROTTLE_TRUSTED_NETWORKS=[ip_network("10.0.0.0/8")])
        ),
    )


async def test_authenticate_user_does_not_throttle_trusted_clients(
    mocker: MockerFixture,
    faker: Faker,
    product: Product,
    mock_throttle: dict[str, AsyncMock],
    mock_trusted_login_settings: MagicMock,
):
    mocker.patch.object(_auth_service, "get_user_or_none", return_value=None)
    mocker.patch.object(_auth_service, "check_authorized_user_credentials", side_effect=WrongPasswordError(user_id=1))

    with pytest.raises(WrongPasswordError):
        await _auth_service.authenticate_user(
            MagicMock(),
            email=faker.email(),
            password="wrong-password",  # noqa: S106
            product=product,
            client_ip=ip_address("10.1.2.3"),
        )

    mock_throttle["raise_if_login_throttled"].assert_not_awaited()
    mock_throttle["register_failed_login"].assert_not_awaited()


async def test_authenticate_user_trusted_client_success_clears_failures(
    mocker: MockerFixture,
    faker: Faker,
    product: Product,
    mock_throttle: dict[str, AsyncMock],
    mock_trusted_login_settings: MagicMock,
):
    expected_user = {"id": 1, "email": faker.email()}
    mocker.patch.object(_auth_service, "get_user_or_none", return_value=expected_user)
    mocker.patch.object(_auth_service, "check_authorized_user_credentials", return_value=expected_user)

    user = await _auth_service.authenticate_user(
        MagicMock(),
        email=expected_user["email"],
        password="correct-password",  # noqa: S106
        product=product,
        client_ip=ip_address("10.1.2.3"),
    )

    assert user == expected_user
    mock_throttle["raise_if_login_throttled"].assert_not_awaited()
    mock_throttle["clear_failed_logins"].assert_awaited_once()


async def test_authenticate_user_throttles_clients_outside_the_trusted_networks(
    mocker: MockerFixture,
    faker: Faker,
    product: Product,
    mock_throttle: dict[str, AsyncMock],
    mock_trusted_login_settings: MagicMock,
):
    mocker.patch.object(_auth_service, "get_user_or_none", return_value=None)
    mocker.patch.object(_auth_service, "check_authorized_user_credentials", side_effect=WrongPasswordError(user_id=1))

    with pytest.raises(WrongPasswordError):
        await _auth_service.authenticate_user(
            MagicMock(),
            email=faker.email(),
            password="wrong-password",  # noqa: S106
            product=product,
            client_ip=ip_address("203.0.113.7"),
        )

    mock_throttle["raise_if_login_throttled"].assert_awaited_once()
    mock_throttle["register_failed_login"].assert_awaited_once()
