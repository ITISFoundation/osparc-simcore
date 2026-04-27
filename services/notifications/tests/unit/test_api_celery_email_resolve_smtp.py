import pytest
from settings_library.email import EmailProtocol, SMTPSettings
from simcore_service_notifications.api.celery._email import (
    _resolve_smtp_settings,
)


def _make_settings(host: str) -> SMTPSettings:
    return SMTPSettings(
        SMTP_HOST=host,
        SMTP_PORT=1025,
        SMTP_PROTOCOL=EmailProtocol.UNENCRYPTED,
    )


def test_resolve_smtp_settings_picks_by_domain():
    a = _make_settings("smtp.a.com")
    b = _make_settings("smtp.b.com")
    smtp_by_domain = {"a.com": a, "b.com": b}

    assert _resolve_smtp_settings(smtp_by_domain, "support@a.com") is a
    assert _resolve_smtp_settings(smtp_by_domain, "support@b.com") is b


def test_resolve_smtp_settings_is_case_insensitive():
    a = _make_settings("smtp.a.com")
    smtp_by_domain = {"A.com": a}

    assert _resolve_smtp_settings(smtp_by_domain, "Support@a.COM") is a


def test_resolve_smtp_settings_unknown_domain_raises():
    a = _make_settings("smtp.a.com")
    with pytest.raises(ValueError, match=r"No SMTP settings configured for domain 'unknown\.com'"):
        _resolve_smtp_settings({"a.com": a}, "support@unknown.com")
