# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

from typing import Any

import pytest
from pydantic import ValidationError
from pytest_simcore.helpers.monkeypatch_envs import delenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from settings_library.email import EmailProtocol, SMTPSettings


@pytest.fixture
def all_env_devel_undefined(
    monkeypatch: pytest.MonkeyPatch, env_devel_dict: EnvVarsDict
) -> None:
    """Ensures that all env vars in .env-devel are undefined in the test environment

    NOTE: this is useful to have a clean starting point and avoid
    the environment to influence your test. I found this situation
    when some script was accidentaly injecting the entire .env-devel in the environment
    """
    delenvs_from_dict(monkeypatch, env_devel_dict, raising=False)


@pytest.mark.parametrize(
    "cfg",
    [
        {
            "SMTP_HOST": "test",
            "SMTP_PORT": 113,
        },
        {
            "SMTP_HOST": "test",
            "SMTP_PORT": 113,
            "SMTP_PROTOCOL": EmailProtocol.UNENCRYPTED,
        },
        {
            "SMTP_HOST": "test",
            "SMTP_PORT": 113,
            "SMTP_USERNAME": "test",
            "SMTP_PASSWORD": "test",
        },
        {
            "SMTP_HOST": "test",
            "SMTP_PORT": 113,
            "SMTP_USERNAME": "test",
            "SMTP_PASSWORD": "test",
            "SMTP_PROTOCOL": EmailProtocol.UNENCRYPTED,
        },
        {
            "SMTP_HOST": "test",
            "SMTP_PORT": 113,
            "SMTP_USERNAME": "test",
            "SMTP_PASSWORD": "test",
            "SMTP_PROTOCOL": EmailProtocol.TLS,
        },
        {
            "SMTP_HOST": "test",
            "SMTP_PORT": 113,
            "SMTP_USERNAME": "test",
            "SMTP_PASSWORD": "test",
            "SMTP_PROTOCOL": EmailProtocol.STARTTLS,
        },
    ],
)
def test_smtp_configuration_ok(cfg: dict[str, Any], all_env_devel_undefined: None):
    assert SMTPSettings.model_validate(cfg)


@pytest.mark.parametrize(
    "cfg",
    [
        {
            "SMTP_HOST": "test",
            "SMTP_PORT": 111,
            "SMTP_USERNAME": "test",
            # password required if username provided
        },
        {
            "SMTP_HOST": "test",
            "SMTP_PORT": 112,
            "SMTP_PASSWORD": "test",
            # username required if password provided
        },
        {
            "SMTP_HOST": "test",
            "SMTP_PORT": 113,
            "SMTP_PROTOCOL": EmailProtocol.STARTTLS,
            "SMTP_PASSWORD": "test",
        },
        {
            "SMTP_HOST": "test",
            "SMTP_PORT": 114,
            "SMTP_PROTOCOL": EmailProtocol.STARTTLS,
            "SMTP_USERNAME": "test",
        },
        {
            "SMTP_HOST": "test",
            "SMTP_PORT": 115,
            "SMTP_USERNAME": "",
            "SMTP_PASSWORD": "test",
            "SMTP_PROTOCOL": EmailProtocol.STARTTLS,
        },
        {
            "SMTP_HOST": "test",
            "SMTP_PORT": 116,
            "SMTP_USERNAME": "",
            "SMTP_PASSWORD": "test",
            "SMTP_PROTOCOL": EmailProtocol.TLS,
        },
    ],
)
def test_smtp_configuration_fails(cfg: dict[str, Any], all_env_devel_undefined: None):
    with pytest.raises(ValidationError):
        SMTPSettings(**cfg)
