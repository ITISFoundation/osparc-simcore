from notifications_library._templates import get_email_templates


def test_templates_organization():
    on_payed_templates = get_email_templates(event_name="on_payed")
    assert set(on_payed_templates) == {
        f"on_payed.email.{suffix}"
        for suffix in ["subject.txt", "content.html", "content.txt"]
    }
