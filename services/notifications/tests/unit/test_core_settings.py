# pylint: disable=unused-variable
# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name


import pytest
from pydantic import ValidationError
from pytest_simcore.helpers.monkeypatch_envs import (
    EnvVarsDict,
)
from simcore_service_notifications.core.settings import (
    ApplicationSettings,
    ProductToSMTPSettings,
    SMTPSettings,
)


def test_valid_application_settings(mock_environment: EnvVarsDict):
    assert mock_environment

    settings = ApplicationSettings()  # type: ignore
    assert settings

    assert settings == ApplicationSettings.create_from_envs()


_SMTP_PAYLOAD = {
    "host": "mailpit",
    "port": 1025,
    "protocol": "UNENCRYPTED",
    "domain": "osparc.io",
    "extra_headers": {},
    "local_parts": {"SUPPORT": "support", "NO_REPLY": "no-reply"},
}


def test_product_smtp_settings_rejects_undefined_profile_reference():
    with pytest.raises(ValidationError, match="undefined SMTP profiles"):
        ProductToSMTPSettings.model_validate(
            {
                "profiles": {"profile_a": _SMTP_PAYLOAD},
                "product_to_profile": {"osparc": "nonexistent_profile"},
            }
        )


def test_product_smtp_settings_get_smtp_settings_for_product():
    product_smtp = ProductToSMTPSettings.model_validate(
        {
            "profiles": {"profile_a": _SMTP_PAYLOAD},
            "product_to_profile": {"osparc": "profile_a"},
        }
    )

    settings = product_smtp.get_smtp_settings_for_product("osparc")

    assert isinstance(settings, SMTPSettings)
    assert settings.host == "mailpit"


def test_product_smtp_settings_unknown_product_raises():
    product_smtp = ProductToSMTPSettings.model_validate(
        {
            "profiles": {"profile_a": _SMTP_PAYLOAD},
            "product_to_profile": {"osparc": "profile_a"},
        }
    )

    with pytest.raises(ValueError, match="No SMTP profile configured for product"):
        product_smtp.get_smtp_settings_for_product("unknown_product")


def test_product_smtp_settings_multiple_products_same_profile():
    product_smtp = ProductToSMTPSettings.model_validate(
        {
            "profiles": {"shared_profile": _SMTP_PAYLOAD},
            "product_to_profile": {"osparc": "shared_profile", "s4l": "shared_profile"},
        }
    )

    assert product_smtp.get_smtp_settings_for_product("osparc") == product_smtp.get_smtp_settings_for_product("s4l")


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
