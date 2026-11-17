# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

from collections.abc import Callable
from typing import Annotated, Any, Final

import pytest
from annotated_types import doc
from pydantic import ValidationError
from simcore_service_notifications.core.settings import SMTPSettings
from simcore_service_notifications.models.smtp import EmailProtocol

_SENTINEL: Final[Annotated[str, doc("unique enough not to appear by accident in an error report")]] = "s3cr3t-SENTINEL"


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


_RENDERERS: Final[dict[str, Callable[[ValidationError], str]]] = {
    "str": str,
    "errors": lambda e: repr(e.errors()),
    "json": lambda e: e.json(),
}


@pytest.mark.parametrize("render", _RENDERERS.values(), ids=_RENDERERS)
@pytest.mark.parametrize(
    "cfg",
    [
        pytest.param(
            {"host": "test", "port": 113, "password": _SENTINEL},
            id="password-without-username",
        ),
        pytest.param(
            {"host": "test", "port": 113, "password": _SENTINEL, "protocol": EmailProtocol.TLS.value},
            id="password-without-username-tls",
        ),
    ],
)
def test_invalid_smtp_configuration_does_not_expose_password(
    cfg: dict[str, Any], render: Callable[[ValidationError], str]
):
    """The credential pairing check is a model-level validator and pydantic reports its
    input verbatim, so the raw password must be masked at validation entry
    """
    with pytest.raises(ValidationError) as err_info:
        SMTPSettings.model_validate(cfg)

    assert _SENTINEL not in render(err_info.value)
