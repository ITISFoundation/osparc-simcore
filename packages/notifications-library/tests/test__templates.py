from pathlib import Path

import pytest
from notifications_library._templates import (
    _templates_dir,
    get_default_named_templates,
    split_template_name,
)


@pytest.mark.parametrize(
    "event_name",
    [
        "on_account_requested",
        "on_change_email",
        "on_new_code",
        "on_new_invitation",
        "on_payed",
        "on_registered",
        "on_reset_password",
        "on_share_project",
        "on_unregister",
    ],
)
def test_email_templates_are_complete(event_name: str):

    event_templates = set(get_default_named_templates(event=event_name, media="email"))

    assert event_templates

    with_html = {
        f"{event_name}.email.{suffix}"
        for suffix in ["subject.txt", "content.html", "content.txt"]
    }
    without_html = {
        f"{event_name}.email.{suffix}" for suffix in ["subject.txt", "content.txt"]
    }

    assert event_templates in (with_html, without_html)


@pytest.mark.parametrize(
    "template_name,template_path", get_default_named_templates().items()
)
def test_named_templates(template_name: str, template_path: Path):

    parts = split_template_name(template_name)
    assert get_default_named_templates(*parts) == {template_name: template_path}


def test_generic_templates():
    assert (_templates_dir / "base.html").exists()

    with pytest.raises(TypeError):
        split_template_name("base.html")
