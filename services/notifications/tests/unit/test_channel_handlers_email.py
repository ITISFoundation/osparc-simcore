import itertools
from collections import Counter

import pytest
from models_library.notifications.rpc import (
    EmailContact,
)
from simcore_service_notifications.services.channel_handlers._email import (
    _interleave_recipients_by_domain,
)


def _contact(email: str) -> EmailContact:
    return EmailContact(name=email.split("@")[0], email=email)


@pytest.mark.parametrize(
    "emails",
    [
        pytest.param([], id="empty"),
        pytest.param(["a@x.com"], id="single"),
    ],
)
def test_interleave_noop_for_trivial_inputs(emails: list[str]):
    contacts = [_contact(e) for e in emails]
    result = _interleave_recipients_by_domain(contacts)
    assert [r.email for r in result] == emails


def test_interleave_spreads_domains():
    contacts = [
        _contact(e)
        for e in [
            "a@gmail.com",
            "b@gmail.com",
            "c@gmail.com",
            "d@yahoo.com",
            "e@yahoo.com",
            "f@outlook.com",
        ]
    ]
    result = _interleave_recipients_by_domain(contacts)
    result_emails = [r.email for r in result]

    # All original recipients are present
    assert Counter(result_emails) == Counter(c.email for c in contacts)

    # No two consecutive emails share the same domain
    domains = [e.split("@")[1] for e in result_emails]
    consecutive_same = sum(1 for a, b in itertools.pairwise(domains) if a == b)
    assert consecutive_same == 0, f"Expected no consecutive same-domain emails, got {consecutive_same}: {domains}"


def test_interleave_preserves_all_recipients():
    contacts = [
        _contact(e)
        for e in [
            "a@a.com",
            "b@a.com",
            "c@b.com",
            "d@b.com",
            "e@c.com",
            "f@c.com",
        ]
    ]
    result = _interleave_recipients_by_domain(contacts)
    assert Counter(r.email for r in result) == Counter(c.email for c in contacts)


def test_interleave_all_same_domain():
    contacts = [_contact(f"u{i}@same.com") for i in range(5)]
    result = _interleave_recipients_by_domain(contacts)
    assert Counter(r.email for r in result) == Counter(c.email for c in contacts)
    assert len(result) == 5


def test_interleave_many_domains_one_each():
    emails = [f"user@domain{i}.com" for i in range(10)]
    contacts = [_contact(e) for e in emails]
    result = _interleave_recipients_by_domain(contacts)
    assert Counter(r.email for r in result) == Counter(emails)
    # All domains are unique, so no consecutive duplicates possible
    domains = [r.email.split("@")[1] for r in result]
    consecutive_same = sum(1 for a, b in itertools.pairwise(domains) if a == b)
    assert consecutive_same == 0
