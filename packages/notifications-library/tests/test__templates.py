import pytest
from notifications_library._templates import get_email_templates


@pytest.mark.parametrize("event_name", ["on_registered", "on_payed"])
def test_get_email_templates(event_name: str):

    event_templates = get_email_templates(event_name=event_name)

    assert set(event_templates) == {
        f"{event_name}.email.{suffix}"
        for suffix in ["subject.txt", "content.html", "content.txt"]
    }
