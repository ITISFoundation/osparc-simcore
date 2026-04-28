# pylint: disable=unused-variable
# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name


import pytest
from pydantic import ValidationError
from pytest_simcore.helpers.monkeypatch_envs import (
    EnvVarsDict,
)
from settings_library.email import SMTPSettings
from simcore_service_notifications.core.settings import (
    ApplicationSettings,
    _PerDomainSMTPSettings,
)


def test_valid_application_settings(mock_environment: EnvVarsDict):
    assert mock_environment

    settings = ApplicationSettings()  # type: ignore
    assert settings

    assert settings == ApplicationSettings.create_from_envs()


_SMTP_PAYLOAD = {
    "SMTP_HOST": "mailpit",
    "SMTP_PORT": 1025,
    "SMTP_PROTOCOL": "UNENCRYPTED",
}


def test_per_domain_smtp_settings_normalizes_keys():
    per_domain = _PerDomainSMTPSettings.model_validate({"  Osparc.IO  ": _SMTP_PAYLOAD})

    assert set(per_domain.root) == {"osparc.io"}


def test_per_domain_smtp_settings_for_email_is_case_insensitive():
    per_domain = _PerDomainSMTPSettings.model_validate({"osparc.io": _SMTP_PAYLOAD})

    settings = per_domain.for_email("Someone <USER@Osparc.IO>")

    assert isinstance(settings, SMTPSettings)
    assert settings.SMTP_HOST == "mailpit"


def test_per_domain_smtp_settings_rejects_duplicate_domains():
    with pytest.raises(ValidationError) as exc_info:
        _PerDomainSMTPSettings.model_validate(
            {
                "osparc.io": _SMTP_PAYLOAD,
                "OSPARC.IO": _SMTP_PAYLOAD,
            }
        )

    assert "Duplicate domains" in str(exc_info.value)


def test_per_domain_smtp_settings_for_email_unknown_domain_raises():
    per_domain = _PerDomainSMTPSettings.model_validate({"osparc.io": _SMTP_PAYLOAD})

    with pytest.raises(ValueError, match="No SMTP settings configured for domain"):
        per_domain.for_email("user@unknown.example")
