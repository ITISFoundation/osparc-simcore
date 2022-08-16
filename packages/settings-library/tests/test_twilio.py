# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import pytest
from pydantic import ValidationError
from pytest import MonkeyPatch
from pytest_simcore.helpers.utils_envs import setenvs_from_dict
from settings_library.twilio import TwilioSettings


def test_twilio_settings_within_envdevel(
    mock_env_devel_environment: dict[str, str], monkeypatch: MonkeyPatch
):
    # in .env-devel these are for the oment undefined
    with pytest.raises(ValidationError):
        TwilioSettings.create_from_envs()

    # adds twilio credentials
    with monkeypatch.context() as patch:
        setenvs_from_dict(
            patch,
            {
                "TWILIO_ACCOUNT_SID": "fake-account",
                "TWILIO_AUTH_TOKEN": "fake-token",
                "TWILIO_MESSAGING_SID": "x" * 34,
            },
        )
        TwilioSettings.create_from_envs()
