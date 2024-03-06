from pathlib import Path

import pytest
from notifications_library._templates import (
    _templates_dir,
    get_default_named_templates,
    split_template_name,
)


@pytest.mark.parametrize("event_name", ["on_registered", "on_payed"])
def test_get_email_templates(event_name: str):

    event_templates = get_default_named_templates(event=event_name, media="email")

    assert set(event_templates) == {
        f"{event_name}.email.{suffix}"
        for suffix in ["subject.txt", "content.html", "content.txt"]
    }


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
