import fnmatch
import logging
from dataclasses import dataclass

from jinja2 import Environment, Template
from models_library.notifications import ChannelType, TemplateName
from pydantic import TypeAdapter

from ..models.content import for_channel
from ..models.template import NotificationTemplate, TemplateRef
from ..templates.registry import get_variables_model

_TEMPLATE_EXTENSION = ".j2"

_logger = logging.getLogger(__name__)


def _build_template(ref: TemplateRef) -> NotificationTemplate:
    return NotificationTemplate(
        ref=ref,
        context_model=get_variables_model(ref),
        parts=for_channel(ref.channel).get_field_names(),
    )


def _matches_pattern(value: str, pattern: str) -> bool:
    """Check if value matches pattern with wildcard support."""
    if pattern == "*":
        return True
    if "*" not in pattern:
        return value == pattern

    # Optimize common wildcard patterns
    if pattern.startswith("*") and pattern.endswith("*"):
        return pattern[1:-1] in value
    if pattern.startswith("*"):
        return value.endswith(pattern[1:])
    if pattern.endswith("*"):
        return value.startswith(pattern[:-1])

    # Use fnmatch for complex patterns
    return fnmatch.fnmatch(value, pattern)


def template_path_prefix(template_ref: TemplateRef) -> str:
    return f"{template_ref.channel}.{template_ref.template_name}"


@dataclass(frozen=True)
class NotificationsTemplatesRepository:
    env: Environment

    @staticmethod
    def _parse_template_path(template_path: str) -> tuple[str, str, str]:
        if not template_path.endswith(_TEMPLATE_EXTENSION):
            raise ValueError(template_path)

        base = template_path.removesuffix(_TEMPLATE_EXTENSION)
        channel, template, part = base.split(".", maxsplit=2)
        return channel, template, part

    def get_jinja_template(
        self,
        template: NotificationTemplate,
        part: str,
    ) -> Template:
        # NOTE: centralized template naming convention
        return self.env.get_template(f"{template_path_prefix(template.ref)}.{part}{_TEMPLATE_EXTENSION}")

    def search_templates(
        self,
        *,
        channel: str | None = None,
        template_name: str | None = None,
        part: str | None = None,
    ) -> list[NotificationTemplate]:
        """Search for notification templates with wildcard support.

        Template path format: {channel}.{template_name}.{part}.j2

        Args:
            channel: Channel filter. Use "*" (default) to match any channel.
            template_name: Template name filter. Use "*" (default) to match any template name.
            part: Part filter. Use "*" (default) to match any part.

        Returns:
            List of matching NotificationTemplate objects.

        Examples:
            search_templates("email", "*", "*")  # All email templates
            search_templates("*", "welcome", "*")  # All welcome templates across channels
            search_templates("email", "user_*", "subject")  # Email templates starting with user_, subject part only
        """

        def filter_func(template_path: str) -> bool:
            if not template_path.endswith(_TEMPLATE_EXTENSION):
                return False

            try:
                channel_str, template_name_str, part_str = self._parse_template_path(template_path)
            except ValueError:
                return False

            return (
                _matches_pattern(channel_str, channel or "*")
                and _matches_pattern(template_name_str, template_name or "*")
                and _matches_pattern(part_str, part or "*")
            )

        # Use dict to deduplicate by (channel, template_name), keeping arbitrary part
        templates_dict: dict[tuple[str, str], NotificationTemplate] = {}

        for template_path in self.env.list_templates(filter_func=filter_func):
            channel_str, template_name_str, _ = self._parse_template_path(template_path)
            key = (channel_str, template_name_str)

            if key not in templates_dict:
                template_ref = TemplateRef(
                    channel=ChannelType(channel_str),
                    template_name=TypeAdapter(TemplateName).validate_python(template_name_str),
                )
                templates_dict[key] = _build_template(template_ref)

        return list(templates_dict.values())
