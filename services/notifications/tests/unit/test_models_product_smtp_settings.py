# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import pytest
from pydantic import ValidationError
from simcore_service_notifications.core.settings import ProductSMTPSettings

_PRODUCT_BASE = {
    "mail_server": "local",
    "domain": "example.com",
    "local_parts": {"support": "support", "no_reply": "no-reply"},
}


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
def test_product_smtp_extra_headers_valid(extra_headers: dict[str, str]):
    cfg = {**_PRODUCT_BASE, "extra_headers": extra_headers}
    settings = ProductSMTPSettings(**cfg)
    assert extra_headers == settings.extra_headers


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
def test_product_smtp_extra_headers_invalid(
    extra_headers: dict[str, str],
    expected_disallowed: list[str],
):
    cfg = {**_PRODUCT_BASE, "extra_headers": extra_headers}
    with pytest.raises(ValidationError) as err_info:
        ProductSMTPSettings(**cfg)

    assert err_info.value.error_count() == 1
    assert err_info.value.errors()[0]["type"] == "value_error"
    error_message = str(err_info.value)
    assert "non-permitted headers" in error_message
    # Check that all expected disallowed headers are mentioned in the error
    for header in expected_disallowed:
        assert header in error_message


def test_product_smtp_extra_headers_case_insensitive_validation():
    """Test that header validation is case-insensitive"""
    valid_variations = [
        {"x-priority": "1"},
        {"X-Priority": "1"},
        {"X-PRIORITY": "1"},
        {"X-PrIoRiTy": "1"},
    ]

    for headers in valid_variations:
        cfg = {**_PRODUCT_BASE, "extra_headers": headers}
        settings = ProductSMTPSettings(**cfg)
        assert headers == settings.extra_headers
