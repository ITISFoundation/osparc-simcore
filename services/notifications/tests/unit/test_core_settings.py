# pylint: disable=unused-variable
# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name


import pytest
from pydantic import TypeAdapter, ValidationError
from pytest_simcore.helpers.monkeypatch_envs import (
    EnvVarsDict,
)
from simcore_service_notifications.core.settings import (
    ApplicationSettings,
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
                "smtp_settings": {"host": "mailpit", "port": 1025, "protocol": "UNENCRYPTED"},
                "domain": "osparc.io",
                "extra_headers": {"x-invalid-header": "value"},
                "local_parts": {"support": "support", "no-reply": "no-reply"},
            }
        )


def test_product_smtp_settings_valid():
    product_smtp = ProductSMTPSettings.model_validate(
        {
            "smtp_settings": {"host": "mailpit", "port": 1025, "protocol": "UNENCRYPTED"},
            "domain": "osparc.io",
            "extra_headers": {},
            "local_parts": {"support": "support", "no-reply": "no-reply"},
        }
    )

    assert isinstance(product_smtp.smtp_settings, SMTPSettings)
    assert product_smtp.smtp_settings.host == "mailpit"


def test_notifications_smtp_settings_dict_structure():
    raw = {
        "osparc": {
            "smtp_settings": {"host": "mailpit", "port": 1025, "protocol": "UNENCRYPTED"},
            "domain": "osparc.io",
            "extra_headers": {},
            "local_parts": {"support": "support", "no-reply": "no-reply"},
        },
        "s4l": {
            "smtp_settings": {"host": "mailpit", "port": 1025, "protocol": "UNENCRYPTED"},
            "domain": "sim4life.io",
            "extra_headers": {},
            "local_parts": {"support": "support", "no-reply": "no-reply"},
        },
    }

    adapter = TypeAdapter(dict[str, ProductSMTPSettings])
    settings = adapter.validate_python(raw)

    assert "osparc" in settings
    assert "s4l" in settings
    assert settings["osparc"].domain == "osparc.io"
    assert settings["s4l"].domain == "sim4life.io"


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
