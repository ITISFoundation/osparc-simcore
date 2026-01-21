from dataclasses import dataclass
from typing import Any

from ..models.preview import NotificationPreview
from ..models.template import NotificationTemplate
from ..repository.templates_repository import NotificationsTemplatesRepository
from .renderer import NotificationsRenderer


@dataclass(frozen=True)
class JinjaNotificationsRenderer(NotificationsRenderer):
    repository: NotificationsTemplatesRepository

    def render_preview(
        self,
        template: NotificationTemplate,
        variables: dict[str, Any],
    ) -> NotificationPreview:
        content = {}
        for render_part in template.parts:
            jinja_template = self.repository.get_jinja_template(template, render_part)

            content[render_part] = jinja_template.render(variables)

        return NotificationPreview(
            template_ref=template.ref, content=self.content_cls_registry[template.ref.channel](**content)
        )
