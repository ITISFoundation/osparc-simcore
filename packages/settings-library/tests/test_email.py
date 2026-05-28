# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

import json
from enum import Enum
from typing import Any

import pytest
from pydantic import ValidationError
from pytest_simcore.helpers.monkeypatch_envs import delenvs_from_dict, setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from settings_library.email import EmailProtocol, SMTPLocals, SMTPSettings

_LOCAL_PARTS = {"SUPPORT": "support", "NO_REPLY": "no-reply"}


@pytest.fixture
def all_env_devel_undefined(monkeypatch: pytest.MonkeyPatch, env_devel_dict: EnvVarsDict) -> None:
    """Ensures that all env vars in .env-devel are undefined in the test environment

    NOTE: this is useful to have a clean starting point and avoid
    the environment to influence your test. I found this situation
    when some script was accidentally injecting the entire .env-devel in the environment
    """
    delenvs_from_dict(monkeypatch, env_devel_dict, raising=False)


@pytest.mark.parametrize(
    "cfg",
    [
        {
            "SMTP_HOST": "test",
            "SMTP_PORT": 113,
            "SMTP_LOCAL_PARTS": _LOCAL_PARTS,
        },
        {
            "SMTP_HOST": "test",
            "SMTP_PORT": 113,
            "SMTP_PROTOCOL": EmailProtocol.UNENCRYPTED.value,
            "SMTP_LOCAL_PARTS": _LOCAL_PARTS,
        },
        {
            "SMTP_HOST": "test",
            "SMTP_PORT": 113,
            "SMTP_USERNAME": "test",
            "SMTP_PASSWORD": "test",
            "SMTP_LOCAL_PARTS": _LOCAL_PARTS,
        },
        {
            "SMTP_HOST": "test",
            "SMTP_PORT": 113,
            "SMTP_USERNAME": "test",
            "SMTP_PASSWORD": "test",
            "SMTP_PROTOCOL": EmailProtocol.UNENCRYPTED.value,
            "SMTP_LOCAL_PARTS": _LOCAL_PARTS,
        },
        {
            "SMTP_HOST": "test",
            "SMTP_PORT": 113,
            "SMTP_USERNAME": "test",
            "SMTP_PASSWORD": "test",
            "SMTP_PROTOCOL": EmailProtocol.TLS.value,
            "SMTP_LOCAL_PARTS": _LOCAL_PARTS,
        },
        {
            "SMTP_HOST": "test",
            "SMTP_PORT": 113,
            "SMTP_USERNAME": "test",
            "SMTP_PASSWORD": "test",
            "SMTP_PROTOCOL": EmailProtocol.STARTTLS.value,
            "SMTP_LOCAL_PARTS": _LOCAL_PARTS,
        },
    ],
)
def test_smtp_configuration_ok(
    all_env_devel_undefined: None,
    monkeypatch: pytest.MonkeyPatch,
    cfg: dict[str, Any],
):
    assert SMTPSettings.model_validate(cfg)

    setenvs_from_dict(
        monkeypatch,
        {k: (json.dumps(v) if isinstance(v, dict) else f"{v}") for k, v in cfg.items()},
    )
    assert SMTPSettings.create_from_envs()


@pytest.mark.parametrize(
    "cfg,error_type",
    [
        (
            {
                "SMTP_HOST": "test",
                "SMTP_PORT": 111,
                "SMTP_USERNAME": "test",
                "SMTP_LOCAL_PARTS": _LOCAL_PARTS,
                # password required if username provided
            },
            "value_error",
        ),
        (
            {
                "SMTP_HOST": "test",
                "SMTP_PORT": 112,
                "SMTP_PASSWORD": "test",
                "SMTP_LOCAL_PARTS": _LOCAL_PARTS,
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
                "SMTP_LOCAL_PARTS": _LOCAL_PARTS,
            },
            "value_error",
        ),
        (
            {
                "SMTP_HOST": "test",
                "SMTP_PORT": 114,
                "SMTP_PROTOCOL": EmailProtocol.STARTTLS,
                "SMTP_USERNAME": "test",
                "SMTP_LOCAL_PARTS": _LOCAL_PARTS,
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
                "SMTP_LOCAL_PARTS": _LOCAL_PARTS,
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
                "SMTP_LOCAL_PARTS": _LOCAL_PARTS,
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


@pytest.mark.parametrize(
    "extra_headers",
    [
        # AWS SES headers - allowed
        {"X-SES-Tenant": "tenant-123"},
        {"X-SES-Configuration-Set": "default"},
        {"x-ses-source-arn": "arn:aws:ses:us-east-1:123456789012:identity/example.com"},
        {"X-SES-FROM-ARN": "arn:aws:ses:us-east-1:123456789012:identity/sender@example.com"},
        {"x-ses-return-path-arn": "arn:aws:ses:us-east-1:123456789012:identity/bounce@example.com"},
        # Delivery metadata headers - allowed
        {"Return-Path": "bounce@example.com"},
        {"X-Mailer": "MyApp 1.0"},
        {"X-Priority": "1 (Highest)"},
        {"x-priority": "3"},  # case insensitive
        {"Precedence": "bulk"},
        {"List-Unsubscribe": "<mailto:unsubscribe@example.com>"},
        {"list-unsubscribe-post": "List-Unsubscribe=One-Click"},
        # Multiple allowed headers
        {"X-SES-Tenant": "tenant-123", "X-Priority": "1"},
        {"Return-Path": "bounce@example.com", "X-Mailer": "MyApp 1.0", "Precedence": "bulk"},
        # Empty dict - allowed
        {},
    ],
)
def test_smtp_extra_headers_valid(
    all_env_devel_undefined: None,
    monkeypatch: pytest.MonkeyPatch,
    extra_headers: dict[str, str],
):
    cfg = {
        "SMTP_HOST": "test",
        "SMTP_PORT": 113,
        "SMTP_EXTRA_HEADERS": extra_headers,
        "SMTP_LOCAL_PARTS": _LOCAL_PARTS,
    }
    settings = SMTPSettings(**cfg)
    assert extra_headers == settings.SMTP_EXTRA_HEADERS


@pytest.mark.parametrize(
    "extra_headers,expected_disallowed",
    [
        # Structural/dangerous headers - not allowed
        ({"From": "sender@example.com"}, ["From"]),
        ({"To": "recipient@example.com"}, ["To"]),
        ({"Subject": "Test Email"}, ["Subject"]),
        ({"Cc": "cc@example.com"}, ["Cc"]),
        ({"Bcc": "bcc@example.com"}, ["Bcc"]),
        ({"Date": "Wed, 27 Feb 2026 12:00:00 +0000"}, ["Date"]),
        ({"Message-ID": "<123@example.com>"}, ["Message-ID"]),
        ({"MIME-Version": "1.0"}, ["MIME-Version"]),
        ({"Content-Type": "text/html"}, ["Content-Type"]),
        # Custom X- headers not in allowed list - not allowed
        ({"X-Custom-Header": "value"}, ["X-Custom-Header"]),
        ({"X-My-App-ID": "12345"}, ["X-My-App-ID"]),
        # Mix of allowed and disallowed
        ({"X-Priority": "1", "From": "sender@example.com"}, ["From"]),
        ({"X-SES-Tenant": "tenant", "Subject": "Test", "To": "test@example.com"}, ["Subject", "To"]),
        # Multiple disallowed
        ({"From": "sender@example.com", "Subject": "Test"}, ["From", "Subject"]),
    ],
)
def test_smtp_extra_headers_invalid(
    all_env_devel_undefined: None,
    monkeypatch: pytest.MonkeyPatch,
    extra_headers: dict[str, str],
    expected_disallowed: list[str],
):
    cfg = {
        "SMTP_HOST": "test",
        "SMTP_PORT": 113,
        "SMTP_EXTRA_HEADERS": extra_headers,
        "SMTP_LOCAL_PARTS": _LOCAL_PARTS,
    }
    with pytest.raises(ValidationError) as err_info:
        SMTPSettings(**cfg)

    assert err_info.value.error_count() == 1
    assert err_info.value.errors()[0]["type"] == "value_error"
    error_message = str(err_info.value)
    assert "non-permitted headers" in error_message
    # Check that all expected disallowed headers are mentioned in the error
    for header in expected_disallowed:
        assert header in error_message


def test_smtp_extra_headers_case_insensitive_validation(
    all_env_devel_undefined: None,
):
    """Test that header validation is case-insensitive"""
    # All these variations should be valid
    valid_variations = [
        {"x-priority": "1"},
        {"X-Priority": "1"},
        {"X-PRIORITY": "1"},
        {"X-PrIoRiTy": "1"},
    ]

    for headers in valid_variations:
        cfg = {
            "SMTP_HOST": "test",
            "SMTP_PORT": 113,
            "SMTP_EXTRA_HEADERS": headers,
            "SMTP_LOCAL_PARTS": _LOCAL_PARTS,
        }
        settings = SMTPSettings(**cfg)
        assert headers == settings.SMTP_EXTRA_HEADERS


def test_smtp_extra_headers_with_envvars(
    all_env_devel_undefined: None,
    monkeypatch: pytest.MonkeyPatch,
):
    """Test SMTP_EXTRA_HEADERS can be set via environment variables"""

    valid_headers = {
        "X-SES-Tenant": "tenant-123",
        "X-Priority": "1",
    }

    setenvs_from_dict(
        monkeypatch,
        {
            "SMTP_HOST": "test",
            "SMTP_PORT": "113",
            "SMTP_EXTRA_HEADERS": json.dumps(valid_headers),
            "SMTP_LOCAL_PARTS": json.dumps(_LOCAL_PARTS),
        },
    )
    settings = SMTPSettings.create_from_envs()
    assert valid_headers == settings.SMTP_EXTRA_HEADERS

    # Test with invalid headers via env vars
    invalid_headers = {"From": "sender@example.com"}
    setenvs_from_dict(
        monkeypatch,
        {
            "SMTP_HOST": "test",
            "SMTP_PORT": "113",
            "SMTP_EXTRA_HEADERS": json.dumps(invalid_headers),
            "SMTP_LOCAL_PARTS": json.dumps(_LOCAL_PARTS),
        },
    )
    with pytest.raises(ValidationError) as err_info:
        SMTPSettings.create_from_envs()
    assert "non-permitted headers" in str(err_info.value)


def test_smtp_locals_requires_fields():
    """SMTPLocals requires SUPPORT and NO_REPLY fields."""
    with pytest.raises(ValidationError) as err_info:
        SMTPLocals()
    assert err_info.value.error_count() == 2

    # Providing both required fields works
    locals_ = SMTPLocals(SUPPORT="support", NO_REPLY="no-reply")
    assert locals_.SUPPORT == "support"
    assert locals_.NO_REPLY == "no-reply"


def test_smtp_locals_custom_values():
    """SMTPLocals accepts custom local-part values."""
    locals_ = SMTPLocals(SUPPORT="help", NO_REPLY="noreply")
    assert locals_.SUPPORT == "help"
    assert locals_.NO_REPLY == "noreply"


def test_smtp_locals_partial_override():
    """SMTPLocals requires all fields; providing only one fails."""
    with pytest.raises(ValidationError) as err_info:
        SMTPLocals(SUPPORT="helpdesk")
    assert err_info.value.error_count() == 1
    assert "NO_REPLY" in str(err_info.value)


def test_smtp_locals_ignores_unknown_keys():
    """SMTPLocals silently drops keys not defined as fields (extra='ignore')."""
    locals_ = SMTPLocals.model_validate(
        {"SUPPORT": "help", "NO_REPLY": "noreply", "UNKNOWN_KEY": "value", "ANOTHER": "x"}
    )
    assert locals_.SUPPORT == "help"
    assert locals_.NO_REPLY == "noreply"
    assert not hasattr(locals_, "UNKNOWN_KEY")
    assert not hasattr(locals_, "ANOTHER")


def test_smtp_settings_with_locals(
    all_env_devel_undefined: None,
):
    """SMTPSettings correctly parses SMTP_LOCAL_PARTS as a nested model."""
    cfg = {
        "SMTP_HOST": "test",
        "SMTP_PORT": 113,
        "SMTP_LOCAL_PARTS": {"SUPPORT": "help", "NO_REPLY": "noreply"},
    }
    settings = SMTPSettings(**cfg)
    assert settings.SMTP_LOCAL_PARTS.SUPPORT == "help"
    assert settings.SMTP_LOCAL_PARTS.NO_REPLY == "noreply"


def test_smtp_settings_locals_required(
    all_env_devel_undefined: None,
):
    """SMTPSettings fails when SMTP_LOCAL_PARTS is not provided."""
    cfg = {
        "SMTP_HOST": "test",
        "SMTP_PORT": 113,
    }
    with pytest.raises(ValidationError):
        SMTPSettings(**cfg)


def test_smtp_settings_locals_ignores_unknown_keys(
    all_env_devel_undefined: None,
):
    """SMTPSettings SMTP_LOCAL_PARTS ignores unrecognized keys from input."""
    cfg = {
        "SMTP_HOST": "test",
        "SMTP_PORT": 113,
        "SMTP_LOCAL_PARTS": {"SUPPORT": "help", "NO_REPLY": "noreply", "INVALID": "garbage"},
    }
    settings = SMTPSettings(**cfg)
    assert settings.SMTP_LOCAL_PARTS.SUPPORT == "help"
    assert not hasattr(settings.SMTP_LOCAL_PARTS, "INVALID")


def test_smtp_settings_locals_with_envvars(
    all_env_devel_undefined: None,
    monkeypatch: pytest.MonkeyPatch,
):
    """SMTP_LOCAL_PARTS can be set via environment variables as JSON."""
    setenvs_from_dict(
        monkeypatch,
        {
            "SMTP_HOST": "test",
            "SMTP_PORT": "113",
            "SMTP_LOCAL_PARTS": json.dumps({"SUPPORT": "helpdesk", "NO_REPLY": "noreply", "EXTRA": "ignored"}),
        },
    )
    settings = SMTPSettings.create_from_envs()
    assert settings.SMTP_LOCAL_PARTS.SUPPORT == "helpdesk"
    assert settings.SMTP_LOCAL_PARTS.NO_REPLY == "noreply"
    assert not hasattr(settings.SMTP_LOCAL_PARTS, "EXTRA")
