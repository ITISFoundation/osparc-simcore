# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import os
from typing import Any

import pytest
from models_library.errors import ErrorDict
from pydantic import ValidationError
from pytest import MonkeyPatch
from pytest_simcore.helpers.utils_envs import setenvs_from_dict
from settings_library.email import SMTPSettings
from simcore_service_webserver.login.settings import LoginOptions, LoginSettings


def test_login_with_invitation(monkeypatch: MonkeyPatch):
    monkeypatch.setenv("LOGIN_REGISTRATION_INVITATION_REQUIRED", "1")

    settings = LoginSettings.create_from_envs()
    assert settings


def test_settings_logging_with_2fa(monkeypatch: MonkeyPatch):

    TWILO_CONFIG = {
        "TWILIO_ACCOUNT_SID": "fake-account",
        "TWILIO_AUTH_TOKEN": "fake-token",
        "TWILIO_MESSAGING_SID": "x" * 34,
    }
    # NOTE: apparently some session-based fixtures is settings these envs
    for key in TWILO_CONFIG.keys():
        monkeypatch.delenv(key, raising=False)

    with monkeypatch.context() as patch:
        setenvs_from_dict(
            patch,
            {
                "LOGIN_REGISTRATION_CONFIRMATION_REQUIRED": "1",
                "LOGIN_REGISTRATION_INVITATION_REQUIRED": "0",
                "LOGIN_2FA_REQUIRED": "1",
                **TWILO_CONFIG,
            },
        )
        LoginSettings.create_from_envs()

    # cannot enable 2fa w/o twilio settings
    with monkeypatch.context() as patch:

        setenvs_from_dict(
            patch,
            {
                "LOGIN_REGISTRATION_CONFIRMATION_REQUIRED": "1",
                "LOGIN_REGISTRATION_INVITATION_REQUIRED": "0",
                "LOGIN_2FA_REQUIRED": "1",
            },
        )
        with pytest.raises(ValidationError) as exc_info:
            LoginSettings.create_from_envs()

        errors: list[ErrorDict] = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("LOGIN_2FA_REQUIRED",)

    # cannot enable 2fa w/o email confirmation
    with monkeypatch.context() as patch:
        setenvs_from_dict(
            patch,
            {
                "LOGIN_REGISTRATION_CONFIRMATION_REQUIRED": "0",
                "LOGIN_REGISTRATION_INVITATION_REQUIRED": "0",
                "LOGIN_2FA_REQUIRED": "1",
                **TWILO_CONFIG,
            },
        )

        with pytest.raises(ValidationError) as exc_info:
            LoginSettings.create_from_envs()

        errors: list[ErrorDict] = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("LOGIN_2FA_REQUIRED",)


def test_smtp_settings(mock_env_devel_environment: dict[str, Any]):

    settings = SMTPSettings()

    cfg = settings.dict(exclude_unset=True)

    for env_name in cfg:
        assert env_name in os.environ

    cfg = settings.dict()

    config = LoginOptions(**cfg)
    print(config.json(indent=1))

    assert config.SMTP_SENDER is not None
