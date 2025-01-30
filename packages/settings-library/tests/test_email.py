# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

from enum import Enum
from typing import Any

import pytest
from pydantic import ValidationError
from pytest_simcore.helpers.monkeypatch_envs import delenvs_from_dict, setenvs_from_dict
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
            "SMTP_PROTOCOL": EmailProtocol.UNENCRYPTED.value,
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
            "SMTP_PROTOCOL": EmailProtocol.UNENCRYPTED.value,
        },
        {
            "SMTP_HOST": "test",
            "SMTP_PORT": 113,
            "SMTP_USERNAME": "test",
            "SMTP_PASSWORD": "test",
            "SMTP_PROTOCOL": EmailProtocol.TLS.value,
        },
        {
            "SMTP_HOST": "test",
            "SMTP_PORT": 113,
            "SMTP_USERNAME": "test",
            "SMTP_PASSWORD": "test",
            "SMTP_PROTOCOL": EmailProtocol.STARTTLS.value,
        },
    ],
)
def test_smtp_configuration_ok(
    all_env_devel_undefined: None,
    monkeypatch: pytest.MonkeyPatch,
    cfg: dict[str, Any],
):
    assert SMTPSettings.model_validate(cfg)

    setenvs_from_dict(monkeypatch, {k: f"{v}" for k, v in cfg.items()})
    assert SMTPSettings.create_from_envs()


@pytest.mark.parametrize(
    "cfg,error_type",
    [
        (
            {
                "SMTP_HOST": "test",
                "SMTP_PORT": 111,
                "SMTP_USERNAME": "test",
                # password required if username provided
            },
            "value_error",
        ),
        (
            {
                "SMTP_HOST": "test",
                "SMTP_PORT": 112,
                "SMTP_PASSWORD": "test",
                # username required if password provided
            },
            "value_error",
        ),
        (
            {
                "SMTP_HOST": "test",
                "SMTP_PORT": 113,
                "SMTP_PROTOCOL": EmailProtocol.STARTTLS,
                "SMTP_PASSWORD": "test",
            },
            "value_error",
        ),
        (
            {
                "SMTP_HOST": "test",
                "SMTP_PORT": 114,
                "SMTP_PROTOCOL": EmailProtocol.STARTTLS,
                "SMTP_USERNAME": "test",
            },
            "value_error",
        ),
        (
            {
                "SMTP_HOST": "test",
                "SMTP_PORT": 115,
                "SMTP_USERNAME": "",
                "SMTP_PASSWORD": "test",
                "SMTP_PROTOCOL": EmailProtocol.STARTTLS,
            },
            "string_too_short",
        ),
        (
            {
                "SMTP_HOST": "test",
                "SMTP_PORT": 116,
                "SMTP_USERNAME": "",
                "SMTP_PASSWORD": "test",
                "SMTP_PROTOCOL": EmailProtocol.TLS,
            },
            "string_too_short",
        ),
    ],
)
def test_smtp_configuration_fails(
    all_env_devel_undefined: None,
    monkeypatch: pytest.MonkeyPatch,
    cfg: dict[str, Any],
    error_type: str,
):
    with pytest.raises(ValidationError) as err_info:
        SMTPSettings(**cfg)

    assert err_info.value.error_count() == 1
    assert err_info.value.errors()[0]["type"] == error_type

    setenvs_from_dict(
        monkeypatch,
        {k: str(v.value if isinstance(v, Enum) else v) for k, v in cfg.items()},
    )
    with pytest.raises(ValidationError) as err_info:
        SMTPSettings.create_from_envs()

    assert err_info.value.error_count() == 1
    assert err_info.value.errors()[0]["type"] == error_type
