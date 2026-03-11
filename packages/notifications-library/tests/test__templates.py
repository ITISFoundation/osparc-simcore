from pathlib import Path

import pytest
from notifications_library._templates import (
    _templates_dir,
    get_default_named_templates,
    split_template_name,
)


@pytest.mark.parametrize(
    "template_name",
    [
        "account_requested",
        "change_email",
        "new_code",
        "new_invitation",
        "paid",
        "registered",
        "reset_password",
        "share_project",
        "unregister",
    ],
)
def test_email_templates_are_complete(template_name: str):
    event_templates = set(get_default_named_templates(template_name=template_name, channel="email"))

    assert event_templates

    with_html = {f"email/{template_name}/{suffix}" for suffix in ["subject.j2", "body_html.j2", "body_text.j2"]}
    without_html = {f"email/{template_name}/{suffix}" for suffix in ["subject.j2", "body_text.j2"]}

    assert event_templates in (with_html, without_html)


@pytest.mark.parametrize("template_name,template_path", get_default_named_templates().items())
def test_named_templates(template_name: str, template_path: Path):
    parts = split_template_name(template_name)
    assert get_default_named_templates(*parts) == {template_name: template_path}


@pytest.mark.parametrize(
    "channel",
    [
        "email",
    ],
)
def test_generic_templates(channel: str):
    assert (_templates_dir / channel / "_base" / "body_html.j2").exists()

    with pytest.raises(TypeError):
        split_template_name("base.html")
