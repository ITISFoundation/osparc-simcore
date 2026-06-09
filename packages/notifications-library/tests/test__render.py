from pathlib import Path

from notifications_library._render import (
    create_render_environment_from_folder,
)
from notifications_library._templates import _print_tree


def test_render_env_from_folder(tmp_path: Path):
    """Test that create_render_environment_from_folder correctly loads templates from a directory."""
    # Create a minimal template structure
    templates_dir = tmp_path / "templates"
    templates_dir.mkdir()

    email_dir = templates_dir / "email" / "test_event"
    email_dir.mkdir(parents=True)
    (email_dir / "subject.j2").write_text("Hello {{ user_name }}")
    (email_dir / "body_text.j2").write_text("Dear {{ user_name }}, this is a test.")

    _print_tree(templates_dir)

    env = create_render_environment_from_folder(templates_dir)

    subject_template = env.get_template("email/test_event/subject.j2")
    body_template = env.get_template("email/test_event/body_text.j2")

    data = {"user_name": "John"}
    assert subject_template.render(data) == "Hello John"
    assert body_template.render(data) == "Dear John, this is a test."


def test_print_tree(tmp_path: Path):
    """Test that _print_tree works without errors."""
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "file.txt").write_text("content")

    # Should not raise
    _print_tree(tmp_path)
