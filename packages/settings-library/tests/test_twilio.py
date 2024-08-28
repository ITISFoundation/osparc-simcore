# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import pytest
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from settings_library.twilio import TwilioSettings


def test_twilio_settings_within_envdevel(
    mock_env_devel_environment: dict[str, str], monkeypatch: pytest.MonkeyPatch
):
    # adds twilio credentials
    with monkeypatch.context() as patch:
        setenvs_from_dict(
            patch,
            {
                "TWILIO_ACCOUNT_SID": "fake-account",
                "TWILIO_AUTH_TOKEN": "fake-token",
            },
        )
        settings = TwilioSettings.create_from_envs()
        print(settings.model_dump_json(indent=2))
        assert settings


def test_twilio_settings_with_country_codes(
    mock_env_devel_environment: dict[str, str], monkeypatch: pytest.MonkeyPatch
):

    # defaults
    with monkeypatch.context() as patch:
        setenvs_from_dict(
            patch,
            {
                "TWILIO_ACCOUNT_SID": "fake-account",
                "TWILIO_AUTH_TOKEN": "fake-token",
            },
        )
        settings = TwilioSettings.create_from_envs()

        assert settings.is_alphanumeric_supported("+41 456 789 156")
        assert not settings.is_alphanumeric_supported(" +1 123456 789 456 ")

    # custom country codes
    with monkeypatch.context() as patch:
        setenvs_from_dict(
            patch,
            {
                "TWILIO_ACCOUNT_SID": "fake-account",
                "TWILIO_AUTH_TOKEN": "fake-token",
                "TWILIO_COUNTRY_CODES_W_ALPHANUMERIC_SID_SUPPORT": "[1, 34]",
            },
        )
        settings = TwilioSettings.create_from_envs()

        assert not settings.is_alphanumeric_supported("+41 456 789 156")
        assert settings.is_alphanumeric_supported(" 001 123456 789 456 ")
        assert settings.is_alphanumeric_supported("+1 123456 789 456 ")
