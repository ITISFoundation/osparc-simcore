from pydantic import SecretStr
from simcore_service_payments.core.settings import ApplicationSettings
from simcore_service_payments.services.auth import authenticate_user


def test_authenticate_user_correct_credentials(auth_settings: ApplicationSettings):
    result = authenticate_user("testuser", "testpass", auth_settings)
    assert result is True


def test_authenticate_user_wrong_username(auth_settings: ApplicationSettings):
    result = authenticate_user("wronguser", "testpass", auth_settings)
    assert result is False


def test_authenticate_user_wrong_password(auth_settings: ApplicationSettings):
    result = authenticate_user("testuser", "wrongpass", auth_settings)
    assert result is False


def test_authenticate_user_both_wrong(auth_settings: ApplicationSettings):
    result = authenticate_user("wronguser", "wrongpass", auth_settings)
    assert result is False


def test_authenticate_user_empty_username(auth_settings: ApplicationSettings):
    result = authenticate_user("", "testpass", auth_settings)
    assert result is False


def test_authenticate_user_empty_password(auth_settings: ApplicationSettings):
    result = authenticate_user("testuser", "", auth_settings)
    assert result is False


def test_authenticate_user_both_empty(auth_settings: ApplicationSettings):
    result = authenticate_user("", "", auth_settings)
    assert result is False


def test_authenticate_user_case_sensitive_username(auth_settings: ApplicationSettings):
    result = authenticate_user("TestUser", "testpass", auth_settings)
    assert result is False


def test_authenticate_user_case_sensitive_password(auth_settings: ApplicationSettings):
    result = authenticate_user("testuser", "TestPass", auth_settings)
    assert result is False


def test_authenticate_user_boundary_ambiguity_prevented(auth_settings: ApplicationSettings):
    auth_settings.PAYMENTS_USERNAME = "testuser"
    auth_settings.PAYMENTS_PASSWORD = SecretStr("pass")

    # This should fail because we use separate comparisons
    result = authenticate_user("test", "userpass", auth_settings)
    assert result is False

    # Correct credentials should pass
    result = authenticate_user("testuser", "pass", auth_settings)
    assert result is True


def test_authenticate_user_with_special_characters(auth_settings: ApplicationSettings):
    auth_settings.PAYMENTS_USERNAME = "user@example.com"
    auth_settings.PAYMENTS_PASSWORD = SecretStr("p@ss!w0rd#")

    result = authenticate_user("user@example.com", "p@ss!w0rd#", auth_settings)
    assert result is True

    result = authenticate_user("user@example.com", "p@ss!w0rd", auth_settings)
    assert result is False


def test_authenticate_user_with_spaces(auth_settings: ApplicationSettings):
    auth_settings.PAYMENTS_USERNAME = "user name"
    auth_settings.PAYMENTS_PASSWORD = SecretStr("pass word")

    result = authenticate_user("user name", "pass word", auth_settings)
    assert result is True

    result = authenticate_user("username", "password", auth_settings)
    assert result is False
