# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

from typing import Any

import pytest
from pydantic import ValidationError
from simcore_service_notifications.core.settings import SMTPSettings
from simcore_service_notifications.models.smtp import EmailProtocol


@pytest.mark.parametrize(
    "cfg",
    [
        {
            "host": "test",
            "port": 113,
        },
        {
            "host": "test",
            "port": 113,
            "protocol": EmailProtocol.UNENCRYPTED.value,
        },
        {
            "host": "test",
            "port": 113,
            "username": "test",
            "password": "test",
        },
        {
            "host": "test",
            "port": 113,
            "username": "test",
            "password": "test",
            "protocol": EmailProtocol.UNENCRYPTED.value,
        },
        {
            "host": "test",
            "port": 113,
            "username": "test",
            "password": "test",
            "protocol": EmailProtocol.TLS.value,
        },
        {
            "host": "test",
            "port": 113,
            "username": "test",
            "password": "test",
            "protocol": EmailProtocol.STARTTLS.value,
        },
    ],
)
def test_smtp_configuration_ok(cfg: dict[str, Any]):
    assert SMTPSettings.model_validate(cfg)


@pytest.mark.parametrize(
    "cfg,error_type",
    [
        (
            {
                "host": "test",
                "port": 111,
                "username": "test",
                # password required if username provided
            },
            "value_error",
        ),
        (
            {
                "host": "test",
                "port": 112,
                "password": "test",
                # username required if password provided
            },
            "value_error",
        ),
        (
            {
                "host": "test",
                "port": 113,
                "protocol": EmailProtocol.STARTTLS.value,
                "password": "test",
            },
            "value_error",
        ),
        (
            {
                "host": "test",
                "port": 114,
                "protocol": EmailProtocol.STARTTLS.value,
                "username": "test",
            },
            "value_error",
        ),
        (
            {
                "host": "test",
                "port": 115,
                "username": "",
                "password": "test",
                "protocol": EmailProtocol.STARTTLS.value,
            },
            "string_too_short",
        ),
        (
            {
                "host": "test",
                "port": 116,
                "username": "",
                "password": "test",
                "protocol": EmailProtocol.TLS.value,
            },
            "string_too_short",
        ),
    ],
)
def test_smtp_configuration_fails(cfg: dict[str, Any], error_type: str):
    with pytest.raises(ValidationError) as err_info:
        SMTPSettings(**cfg)

    assert err_info.value.error_count() == 1
    assert err_info.value.errors()[0]["type"] == error_type
