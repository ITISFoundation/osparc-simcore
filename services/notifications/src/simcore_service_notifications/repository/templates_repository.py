from dataclasses import dataclass

from jinja2 import Environment, Template

from simcore_service_notifications.variables.registry import get_variables_model

from ..models.template import EmailNotificationTemplate, NotificationTemplate, TemplateRef


def template_path_prefix(template_ref: TemplateRef) -> str:
    return f"{template_ref.channel}.{template_ref.template_name}"


@dataclass(frozen=True)
class NotificationsTemplatesRepository:
    env: Environment

    def _parse_template_path(self, template_path: str) -> tuple[str, str, str]:
        if not template_path.endswith(".j2"):
            raise ValueError(template_path)

        base = template_path.removesuffix(".j2")
        channel, template, part = base.split(".", maxsplit=2)
        return channel, template, part

    def get_jinja_template(
        self,
        template: NotificationTemplate,
        part: str,
    ) -> Template:
        # NOTE: centralized template naming convention
        return self.env.get_template(f"{template_path_prefix(template.ref)}.{part}.j2")

    def get_template(self, ref: TemplateRef) -> NotificationTemplate:
        return EmailNotificationTemplate(
            ref=ref,
            variables_model=get_variables_model(ref),
        )
