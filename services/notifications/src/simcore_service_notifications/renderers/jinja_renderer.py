from dataclasses import dataclass
from typing import Any

from ..channels.content_registry import get_content_cls
from ..models.preview import NotificationTemplatePreview
from ..models.template import NotificationTemplate
from ..repository.templates_repository import NotificationsTemplatesRepository
from .renderer import NotificationsRenderer


@dataclass(frozen=True)
class JinjaNotificationsRenderer(NotificationsRenderer):
    repository: NotificationsTemplatesRepository

    def preview_template(
        self,
        template: NotificationTemplate,
        context: dict[str, Any],
    ) -> NotificationTemplatePreview:
        content = {}
        for render_part in template.parts:
            jinja_template = self.repository.get_jinja_template(template, render_part)

            content[render_part] = jinja_template.render(context)

        return NotificationTemplatePreview(
            template_ref=template.ref,
            content=get_content_cls(template.ref.channel)(**content),
        )
