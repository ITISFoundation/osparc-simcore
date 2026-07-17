# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import pytest
from pydantic import ValidationError
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from simcore_postgres_database.models.products import ProductLoginSettingsDict
from simcore_service_webserver.login.settings import (
    LoginSettings,
    LoginSettingsForProduct,
)


def test_login_with_invitation(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("LOGIN_REGISTRATION_INVITATION_REQUIRED", "1")

    settings = LoginSettings.create_from_envs()
    assert settings


@pytest.fixture
def twilio_config(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    TWILO_CONFIG = {
        "TWILIO_ACCOUNT_SID": "fake-account",
        "TWILIO_AUTH_TOKEN": "fake-token",
        "TWILIO_MESSAGING_SID": "x" * 34,
    }
    # NOTE: enforces DELETE-ENV since apparently some session-based fixtures are settings these envs
    for key in TWILO_CONFIG:
        monkeypatch.delenv(key, raising=False)
    return TWILO_CONFIG


def test_login_settings_with_2fa(monkeypatch: pytest.MonkeyPatch, twilio_config: dict[str, str]):
    setenvs_from_dict(
        monkeypatch,
        {
            "LOGIN_REGISTRATION_INVITATION_REQUIRED": "0",
            **twilio_config,
        },
    )
    assert LoginSettingsForProduct.create_from_envs(LOGIN_2FA_REQUIRED=1)


def test_login_settings_fails_with_2fa_but_wo_twilio(monkeypatch: pytest.MonkeyPatch, twilio_config: dict[str, str]):
    # cannot enable 2fa w/o twilio settings
    setenvs_from_dict(
        monkeypatch,
        {
            "LOGIN_REGISTRATION_INVITATION_REQUIRED": "0",
        },
    )
    with pytest.raises(ValidationError) as exc_info:
        LoginSettingsForProduct.create_from_envs(LOGIN_2FA_REQUIRED=1)

    assert exc_info.value
    errors = exc_info.value.errors()
    assert len(errors) == 1
    assert errors[0]["loc"] == ("LOGIN_2FA_REQUIRED",)


def test_product_login_settings_in_plugin_settings():
    # pylint: disable=no-member
    customizable_attributes = set(ProductLoginSettingsDict.__annotations__.keys())
    settings_attributes = set(LoginSettingsForProduct.model_fields.keys())

    assert customizable_attributes.issubset(settings_attributes)
