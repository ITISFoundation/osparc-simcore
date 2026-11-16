import pytest
from pydantic import SecretStr
from simcore_service_payments.core.settings import ApplicationSettings
from simcore_service_payments.services.auth import authenticate_user


@pytest.mark.parametrize(
    "username,password,expected",
    [
        ("testuser", "testpass", True),
        ("wronguser", "testpass", False),
        ("testuser", "wrongpass", False),
        ("wronguser", "wrongpass", False),
        ("", "testpass", False),
        ("testuser", "", False),
        ("", "", False),
        ("TestUser", "testpass", False),
        ("testuser", "TestPass", False),
    ],
)
def test_authenticate_user(auth_settings: ApplicationSettings, username: str, password: str, expected: bool):
    result = authenticate_user(username, password, auth_settings)
    assert result is expected


def test_authenticate_user_boundary_collision_prevention(auth_settings: ApplicationSettings):
    auth_settings.PAYMENTS_USERNAME = "testuser"
    auth_settings.PAYMENTS_PASSWORD = SecretStr("pass")

    result = authenticate_user("test", "userpass", auth_settings)
    assert result is False

    result = authenticate_user("testuser", "pass", auth_settings)
    assert result is True
