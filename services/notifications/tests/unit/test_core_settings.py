# pylint: disable=unused-variable
# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name


import json
from typing import Any, Final

import pytest
from celery_library.basic_types import BootServerMode
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
from simcore_service_notifications.exceptions.errors import (
    InvalidNotificationsChannelSettingsError,
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
    monkeypatch.setenv("NOTIFICATIONS_BOOT_SERVER_MODE", "AS_CELERY_WORKER")
    monkeypatch.delenv("NOTIFICATIONS_SMTP_SETTINGS", raising=False)

    with pytest.raises(ValidationError, match="NOTIFICATIONS_SMTP_SETTINGS must be configured"):
        ApplicationSettings.create_from_envs()


def test_worker_mode_with_smtp_settings_is_valid(mock_environment: EnvVarsDict, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("NOTIFICATIONS_BOOT_SERVER_MODE", "AS_CELERY_WORKER")

    settings = ApplicationSettings.create_from_envs()

    assert settings.NOTIFICATIONS_BOOT_SERVER_MODE is BootServerMode.AS_CELERY_WORKER
    assert settings.NOTIFICATIONS_SMTP_SETTINGS is not None


def test_worker_channel_queue_requires_matching_settings(
    mock_environment: EnvVarsDict, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("NOTIFICATIONS_BOOT_SERVER_MODE", "AS_CELERY_WORKER")
    monkeypatch.setenv("NOTIFICATIONS_CELERY_QUEUES", "notifications-email")
    monkeypatch.delenv("NOTIFICATIONS_SMTP_SETTINGS", raising=False)

    with pytest.raises(ValidationError, match="consumes the 'email' channel"):
        ApplicationSettings.create_from_envs()


def test_worker_channel_queue_with_settings_is_valid(mock_environment: EnvVarsDict, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("NOTIFICATIONS_BOOT_SERVER_MODE", "AS_CELERY_WORKER")
    monkeypatch.setenv("NOTIFICATIONS_CELERY_QUEUES", " notifications-email ")

    settings = ApplicationSettings.create_from_envs()

    assert settings.NOTIFICATIONS_CELERY_QUEUES == " notifications-email "
    assert settings.NOTIFICATIONS_SMTP_SETTINGS is not None


@pytest.mark.parametrize("queue", ["notifications", "cpu_bound"])
def test_worker_rejects_queue_that_is_not_a_channel_queue(
    mock_environment: EnvVarsDict, monkeypatch: pytest.MonkeyPatch, queue: str
):
    """The pre-rename 'notifications' queue name must fail at boot instead of
    silently starting a worker that consumes nothing"""
    monkeypatch.setenv("NOTIFICATIONS_BOOT_SERVER_MODE", "AS_CELERY_WORKER")
    monkeypatch.setenv("NOTIFICATIONS_CELERY_QUEUES", queue)

    with pytest.raises(ValidationError, match="not a notifications per-channel queue"):
        ApplicationSettings.create_from_envs()


def test_api_server_mode_does_not_require_channel_settings(
    mock_environment: EnvVarsDict, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.delenv("NOTIFICATIONS_BOOT_SERVER_MODE", raising=False)
    monkeypatch.setenv("NOTIFICATIONS_CELERY_QUEUES", "notifications-email")
    monkeypatch.delenv("NOTIFICATIONS_SMTP_SETTINGS", raising=False)

    settings = ApplicationSettings.create_from_envs()

    assert settings.NOTIFICATIONS_BOOT_SERVER_MODE is BootServerMode.AS_REST_API_SERVER


def test_non_worker_mode_allows_missing_smtp_settings(mock_environment: EnvVarsDict, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("NOTIFICATIONS_BOOT_SERVER_MODE", "AS_REST_API_SERVER")
    monkeypatch.delenv("NOTIFICATIONS_SMTP_SETTINGS", raising=False)

    settings = ApplicationSettings.create_from_envs()

    assert settings.NOTIFICATIONS_BOOT_SERVER_MODE is BootServerMode.AS_REST_API_SERVER
    assert settings.NOTIFICATIONS_SMTP_SETTINGS is None


_TWILIO_SETTINGS: Final[dict[str, Any]] = {
    "accounts": {
        "local": {
            "TWILIO_ACCOUNT_SID": "ACdummy",
            "TWILIO_AUTH_TOKEN": "aDummyAuthToken",
            "TWILIO_COUNTRY_CODES_W_ALPHANUMERIC_SID_SUPPORT": ["41"],
        }
    },
    "products": {
        "osparc": {
            "account": "local",
            "messaging_service_sid": "MGdummy",
            "alphanumeric_sender_id": "osparc",
        }
    },
}


def test_twilio_settings_valid(mock_environment: EnvVarsDict, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("NOTIFICATIONS_TWILIO_SETTINGS", json.dumps(_TWILIO_SETTINGS))

    settings = ApplicationSettings.create_from_envs()

    assert settings.NOTIFICATIONS_TWILIO_SETTINGS is not None
    assert settings.NOTIFICATIONS_TWILIO_SETTINGS.get_twilio_account_settings("osparc").TWILIO_ACCOUNT_SID == "ACdummy"


def test_twilio_settings_empty_string_is_unset(mock_environment: EnvVarsDict, monkeypatch: pytest.MonkeyPatch):
    # e.g. `NOTIFICATIONS_TWILIO_SETTINGS: ${TWILIO_SETTINGS}` with TWILIO_SETTINGS unset
    monkeypatch.setenv("NOTIFICATIONS_TWILIO_SETTINGS", "")

    settings = ApplicationSettings.create_from_envs()

    assert settings.NOTIFICATIONS_TWILIO_SETTINGS is None


def test_twilio_settings_malformed_json_fails_without_echoing_secret(
    mock_environment: EnvVarsDict, monkeypatch: pytest.MonkeyPatch
):
    probe_value = "dummyAuthTokenA"
    monkeypatch.setenv("NOTIFICATIONS_TWILIO_SETTINGS", '{"accounts": {"TWILIO_AUTH_TOKEN": "' + probe_value + '"')

    with pytest.raises(InvalidNotificationsChannelSettingsError) as exc_info:
        ApplicationSettings.create_from_envs()

    assert "NOTIFICATIONS_TWILIO_SETTINGS" in str(exc_info.value)
    assert probe_value not in str(exc_info.value)


def test_smtp_settings_malformed_json_fails_without_echoing_password(
    mock_environment: EnvVarsDict, monkeypatch: pytest.MonkeyPatch
):
    probe_value = "dummySmtpPasswordB"
    monkeypatch.setenv("NOTIFICATIONS_SMTP_SETTINGS", '{"mail_servers": {"password": "' + probe_value + '"')

    with pytest.raises(InvalidNotificationsChannelSettingsError) as exc_info:
        ApplicationSettings.create_from_envs()

    assert "NOTIFICATIONS_SMTP_SETTINGS" in str(exc_info.value)
    assert probe_value not in str(exc_info.value)
