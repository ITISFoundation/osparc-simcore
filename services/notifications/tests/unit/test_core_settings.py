# pylint: disable=unused-variable
# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name


import pytest
from models_library.notifications.errors import (
    NotificationsProductSMTPSettingsNotFoundError,
)
from pydantic import ValidationError
from pytest_simcore.helpers.monkeypatch_envs import (
    EnvVarsDict,
)
from simcore_service_notifications.core.settings import (
    ApplicationSettings,
    NotificationsSMTPSettings,
    ProductSMTPSettings,
    SMTPSettings,
)


def test_valid_application_settings(mock_environment: EnvVarsDict):
    assert mock_environment

    settings = ApplicationSettings()  # type: ignore
    assert settings

    assert settings == ApplicationSettings.create_from_envs()


def test_product_smtp_settings_rejects_disallowed_headers():
    with pytest.raises(ValidationError):
        ProductSMTPSettings.model_validate(
            {
                "mail_server": "aws",
                "domain": "osparc.io",
                "extra_headers": {"x-invalid-header": "value"},
                "local_parts": {"support": "support", "no_reply": "no-reply"},
            }
        )


def test_product_smtp_settings_valid():
    product_smtp = ProductSMTPSettings.model_validate(
        {
            "mail_server": "aws",
            "domain": "osparc.io",
            "extra_headers": {},
            "local_parts": {"support": "support", "no_reply": "no-reply"},
        }
    )

    assert product_smtp.mail_server == "aws"
    assert product_smtp.domain == "osparc.io"


def test_notifications_smtp_settings_structure():
    raw = {
        "mail_servers": {
            "aws": {"host": "mailpit", "port": 1025, "protocol": "UNENCRYPTED"},
        },
        "products": {
            "osparc": {
                "mail_server": "aws",
                "domain": "osparc.io",
                "extra_headers": {},
                "local_parts": {"support": "support", "no_reply": "no-reply"},
            },
            "s4l": {
                "mail_server": "aws",
                "domain": "sim4life.io",
                "extra_headers": {},
                "local_parts": {"support": "support", "no_reply": "no-reply"},
            },
        },
    }

    settings = NotificationsSMTPSettings.model_validate(raw)

    assert "osparc" in settings.products
    assert "s4l" in settings.products
    assert settings.products["osparc"].domain == "osparc.io"
    assert settings.products["s4l"].domain == "sim4life.io"
    assert isinstance(settings.get_smtp_settings("osparc"), SMTPSettings)


def test_notifications_smtp_settings_rejects_invalid_mail_server_reference():
    raw = {
        "mail_servers": {
            "aws": {"host": "mailpit", "port": 1025, "protocol": "UNENCRYPTED"},
        },
        "products": {
            "osparc": {
                "mail_server": "nonexistent",
                "domain": "osparc.io",
                "extra_headers": {},
                "local_parts": {"support": "support", "no_reply": "no-reply"},
            },
        },
    }

    with pytest.raises(ValidationError, match="nonexistent"):
        NotificationsSMTPSettings.model_validate(raw)


def test_notifications_smtp_settings_get_unknown_product_raises():
    settings = NotificationsSMTPSettings.model_validate(
        {
            "mail_servers": {
                "aws": {"host": "mailpit", "port": 1025, "protocol": "UNENCRYPTED"},
            },
            "products": {
                "osparc": {
                    "mail_server": "aws",
                    "domain": "osparc.io",
                    "extra_headers": {},
                    "local_parts": {"support": "support", "no_reply": "no-reply"},
                },
            },
        }
    )

    with pytest.raises(NotificationsProductSMTPSettingsNotFoundError, match="unknown_product"):
        settings.get_product_smtp_settings("unknown_product")

    with pytest.raises(NotificationsProductSMTPSettingsNotFoundError, match="unknown_product"):
        settings.get_smtp_settings("unknown_product")


def test_worker_mode_requires_smtp_settings(mock_environment: EnvVarsDict, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("NOTIFICATIONS_WORKER_MODE", "true")
    monkeypatch.delenv("NOTIFICATIONS_SMTP_SETTINGS", raising=False)

    with pytest.raises(ValidationError, match="NOTIFICATIONS_SMTP_SETTINGS must be configured"):
        ApplicationSettings.create_from_envs()


def test_worker_mode_with_smtp_settings_is_valid(mock_environment: EnvVarsDict, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("NOTIFICATIONS_WORKER_MODE", "true")

    settings = ApplicationSettings.create_from_envs()

    assert settings.NOTIFICATIONS_WORKER_MODE is True
    assert settings.NOTIFICATIONS_SMTP_SETTINGS is not None


def test_non_worker_mode_allows_missing_smtp_settings(mock_environment: EnvVarsDict, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("NOTIFICATIONS_WORKER_MODE", "false")
    monkeypatch.delenv("NOTIFICATIONS_SMTP_SETTINGS", raising=False)

    settings = ApplicationSettings.create_from_envs()

    assert settings.NOTIFICATIONS_WORKER_MODE is False
    assert settings.NOTIFICATIONS_SMTP_SETTINGS is None
