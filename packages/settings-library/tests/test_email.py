# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

from typing import Any

import pytest
from pydantic import ValidationError
from settings_library.email import EmailProtocol, SMTPSettings


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
    assert SMTPSettings.parse_obj(cfg)


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
