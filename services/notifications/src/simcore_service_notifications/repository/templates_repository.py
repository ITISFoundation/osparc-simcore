import fnmatch
import logging
from dataclasses import dataclass

from jinja2 import Environment, Template
from models_library.notifications import ChannelType, TemplateName
from pydantic import TypeAdapter

from ..models.content import for_channel
from ..models.template import NotificationTemplate, TemplateRef
from ..templates.registry import get_context_model

_TEMPLATE_EXTENSION = ".j2"

_logger = logging.getLogger(__name__)


def _build_template(ref: TemplateRef) -> NotificationTemplate:
    return NotificationTemplate(
        ref=ref,
        context_model=get_context_model(ref),
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
    return f"{template_ref.channel}/{template_ref.template_name}"


@dataclass(frozen=True)
class NotificationsTemplatesRepository:
    env: Environment

    @staticmethod
    def _parse_template_path(template_path: str) -> tuple[str, str, str]:
        """Parse template path in format: {channel}/{template_name}.{part}.j2

        Examples:
            email/account_approved.body_html.j2 -> ("email", "account_approved", "body_html")
            email/account_approved.body_text.j2 -> ("email", "account_approved", "body_text")
            email/account_approved.subject.j2 -> ("email", "account_approved", "subject")
        """
        if not template_path.endswith(_TEMPLATE_EXTENSION):
            raise ValueError(template_path)

        # Remove .j2 extension
        base = template_path.removesuffix(_TEMPLATE_EXTENSION)

        # Split channel from rest: "email/account_approved.body_html" -> "email", "account_approved.body_html"
        if "/" not in base:
            msg = f"Template path must include channel folder: {template_path}"
            raise ValueError(msg)

        channel, rest = base.split("/", maxsplit=1)

        # Split template name from part: "account_approved.body_html" -> "account_approved", "body_html"
        # Template name is the first segment, part is everything after the first dot
        if "." not in rest:
            msg = f"Template path must include part after template name: {template_path}"
            raise ValueError(msg)

        template_name, part = rest.split(".", maxsplit=1)
        return channel, template_name, part

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
        channel: ChannelType | None = None,
        template_name: str | None = None,
        part: str | None = None,
    ) -> list[NotificationTemplate]:
        """Search for notification templates with wildcard support for template_name and part.

        Template path format: {channel}/{template_name}.{part}.j2

        Args:
            channel: Channel filter (exact match, no wildcards). If None, searches all channels.
            template_name: Template name filter. Use "*" (default) to match any template name.
                          Supports wildcards like "user_*" or "*_welcome".
            part: Part filter. Use "*" (default) to match any part.
                  Supports wildcards.

        Returns:
            List of matching NotificationTemplate objects.

        Examples:
            search_templates(ChannelType.email)  # All email templates
            search_templates(None, "welcome")  # All welcome templates across all channels
            search_templates(ChannelType.email, "user_*", "subject")  # Email templates starting with user_,
            subject part only
        """

        def filter_func(template_path: str) -> bool:
            if not template_path.endswith(_TEMPLATE_EXTENSION):
                return False

            try:
                channel_str, template_name_str, part_str = self._parse_template_path(template_path)
            except ValueError:
                return False

            # Channel filtering: exact match only, no wildcards
            if channel is not None and channel_str != channel.value:
                return False

            return _matches_pattern(template_name_str, template_name or "*") and _matches_pattern(part_str, part or "*")

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
