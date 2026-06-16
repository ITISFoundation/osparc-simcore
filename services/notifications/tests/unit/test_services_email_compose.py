# pylint: disable=redefined-outer-name

import re
from email.headerregistry import Address
from email.utils import parsedate_to_datetime

import pytest
from simcore_service_notifications.services.email import compose_email


@pytest.fixture
def sender_address() -> Address:
    return Address(display_name="Support", addr_spec="support@example.com")


@pytest.fixture
def recipient_address() -> Address:
    return Address(display_name="User", addr_spec="user@test.com")


def test_compose_email_sets_date_header(
    sender_address: Address,
    recipient_address: Address,
):
    msg = compose_email(
        from_=sender_address,
        to=recipient_address,
        subject="Test",
        content_text="Hello",
    )

    assert msg["Date"] is not None
    # Verify it parses as a valid RFC 5322 date
    parsed = parsedate_to_datetime(msg["Date"])
    assert parsed is not None


def test_compose_email_sets_message_id_header(
    sender_address: Address,
    recipient_address: Address,
):
    msg = compose_email(
        from_=sender_address,
        to=recipient_address,
        subject="Test",
        content_text="Hello",
    )

    assert msg["Message-ID"] is not None
    # Message-ID must use the sender's domain
    assert "@example.com>" in msg["Message-ID"]


def test_compose_email_message_id_uses_sender_domain(
    recipient_address: Address,
):
    sender = Address(display_name="Ops", addr_spec="noreply@mydomain.org")
    msg = compose_email(
        from_=sender,
        to=recipient_address,
        subject="Test",
        content_text="Hello",
    )

    assert "@mydomain.org>" in msg["Message-ID"]


def test_compose_email_message_id_is_unique_per_call(
    sender_address: Address,
    recipient_address: Address,
):
    msg1 = compose_email(
        from_=sender_address,
        to=recipient_address,
        subject="Test 1",
        content_text="Hello",
    )
    msg2 = compose_email(
        from_=sender_address,
        to=recipient_address,
        subject="Test 2",
        content_text="Hello",
    )

    assert msg1["Message-ID"] != msg2["Message-ID"]


def test_compose_email_message_id_format(
    sender_address: Address,
    recipient_address: Address,
):
    msg = compose_email(
        from_=sender_address,
        to=recipient_address,
        subject="Test",
        content_text="Hello",
    )

    # RFC 5322 Message-ID format: <local-part@domain>
    assert re.match(r"^<.+@example\.com>$", msg["Message-ID"])


def test_compose_email_date_has_timezone_offset(
    sender_address: Address,
    recipient_address: Address,
):
    msg = compose_email(
        from_=sender_address,
        to=recipient_address,
        subject="Test",
        content_text="Hello",
    )

    # Must NOT contain -0000 (unknown timezone), should have a real offset
    assert "-0000" not in msg["Date"]
