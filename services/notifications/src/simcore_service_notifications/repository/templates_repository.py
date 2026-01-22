import logging
from dataclasses import dataclass, fields

from jinja2 import Environment, Template

from ..content.registry import get_content_cls
from ..models.channel import ChannelType
from ..models.template import NotificationTemplate, TemplateRef
from ..variables.registry import get_variables_model

_TEMPLATE_EXTENSION = ".j2"

_logger = logging.getLogger(__name__)


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

    @staticmethod
    def get_template(ref: TemplateRef) -> NotificationTemplate:
        return NotificationTemplate(
            ref=ref,
            variables_model=get_variables_model(ref),
            parts=tuple(f.name for f in fields(get_content_cls(ref.channel))),  # type: ignore[arg-type]
        )

    def list_templates(self, channel: ChannelType) -> list[NotificationTemplate]:
        templates = set()
        prefix = f"{channel}."
        for template_name in self.env.list_templates():
            if not template_name.startswith(prefix) or not template_name.endswith(_TEMPLATE_EXTENSION):
                continue

            _, template, _ = self._parse_template_path(template_name)
            template_ref = TemplateRef(channel=channel, template_name=template)
            templates.add(self.get_template(template_ref))

        return list(templates)
