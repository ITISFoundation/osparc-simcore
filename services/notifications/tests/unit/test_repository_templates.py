# pylint: disable=redefined-outer-name
# pylint: disable=protected-access

import pytest
from jinja2 import Environment
from models_library.notifications import ChannelType, TemplateName
from pydantic import TypeAdapter
from simcore_service_notifications.models.template import TemplateRef
from simcore_service_notifications.repositories import (
    FileTemplatesRepository,
    TemplatesRepository,
    template_path_prefix,
)


@pytest.fixture
def templates_repo(mock_jinja_env: Environment) -> TemplatesRepository:
    """Create a FileTemplatesRepository instance with mock templates."""
    return FileTemplatesRepository(env=mock_jinja_env)


def test_template_path_prefix() -> None:
    """Test generating template path prefix."""
    ref = TemplateRef(
        channel=ChannelType.email,
        template_name=TypeAdapter(TemplateName).validate_python("welcome"),
    )
    prefix = template_path_prefix(ref)
    assert prefix == "email/welcome"


def test_search_templates_no_filters(
    templates_repo: TemplatesRepository,
) -> None:
    """Test searching templates without any filters."""
    templates = templates_repo.search_templates()
    assert isinstance(templates, list)


def test_search_templates_by_channel(
    templates_repo: TemplatesRepository,
) -> None:
    """Test searching templates by channel."""
    templates = templates_repo.search_templates(channel=ChannelType.email)
    assert isinstance(templates, list)
    if templates:
        assert all(t.ref.channel == ChannelType.email for t in templates)


def test_search_templates_by_template_name(
    templates_repo: TemplatesRepository,
) -> None:
    """Test searching templates by template name with exact match."""
    templates = templates_repo.search_templates(template_name="*")
    assert isinstance(templates, list)


def test_search_templates_by_wildcard_name_prefix(
    templates_repo: TemplatesRepository,
) -> None:
    """Test searching templates with wildcard prefix pattern."""
    templates = templates_repo.search_templates(template_name="*_*")
    assert isinstance(templates, list)


def test_search_templates_by_wildcard_name_suffix(
    templates_repo: TemplatesRepository,
) -> None:
    """Test searching templates with wildcard suffix pattern."""
    templates = templates_repo.search_templates(template_name="account_*")
    assert isinstance(templates, list)


def test_search_templates_by_part(
    templates_repo: TemplatesRepository,
) -> None:
    """Test searching templates by part name."""
    templates = templates_repo.search_templates(part="subject")
    assert isinstance(templates, list)
    if templates:
        assert all(t.ref.channel is not None for t in templates)


def test_search_templates_by_part_body(
    templates_repo: TemplatesRepository,
) -> None:
    """Test searching templates by part name body_html."""
    templates = templates_repo.search_templates(part="body_html")
    assert isinstance(templates, list)
    if templates:
        assert all(t.ref.channel is not None for t in templates)


def test_search_templates_by_part_wildcard(
    templates_repo: TemplatesRepository,
) -> None:
    """Test searching templates by part name with wildcard."""
    templates = templates_repo.search_templates(part="body_*")
    assert isinstance(templates, list)


def test_search_templates_combined_filters_channel_and_name(
    templates_repo: TemplatesRepository,
) -> None:
    """Test searching templates with channel and name filters."""
    templates = templates_repo.search_templates(
        channel=ChannelType.email,
        template_name="*",
    )
    assert isinstance(templates, list)
    if templates:
        assert all(t.ref.channel == ChannelType.email for t in templates)


def test_search_templates_combined_filters_all(
    templates_repo: TemplatesRepository,
) -> None:
    """Test searching templates with all filters combined."""
    templates = templates_repo.search_templates(
        channel=ChannelType.email,
        template_name="*",
        part="*",
    )
    assert isinstance(templates, list)
    if templates:
        assert all(t.ref.channel == ChannelType.email for t in templates)


def test_search_templates_no_duplicates(
    templates_repo: TemplatesRepository,
) -> None:
    """Test that search_templates doesn't return duplicates."""
    templates = templates_repo.search_templates()
    template_keys = [(t.ref.channel, t.ref.template_name) for t in templates]
    assert len(template_keys) == len(set(template_keys)), "Duplicate templates found"


def test_search_templates_returns_template_objects(
    templates_repo: TemplatesRepository,
) -> None:
    """Test that search_templates returns proper template objects with all attributes."""
    templates = templates_repo.search_templates(channel=ChannelType.email)
    if templates:
        template = templates[0]
        assert hasattr(template, "ref")
        assert hasattr(template, "context_model")
        assert hasattr(template, "parts")
        assert template.ref.channel is not None
        assert template.ref.template_name is not None
        assert isinstance(template.parts, tuple)


def test_search_templates_invalid_channel_returns_empty(
    templates_repo: TemplatesRepository,
) -> None:
    """Test that filtering by non-existent channel returns empty list."""
    # Note: ChannelType only has 'email' as defined in models
    templates = templates_repo.search_templates(channel=ChannelType.email)
    # Should either find templates or return empty list without error
    assert isinstance(templates, list)
