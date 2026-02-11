from dataclasses import dataclass
from typing import Any

from ..models.content import for_channel
from ..models.preview import NotificationTemplatePreview
from ..models.template import NotificationsTemplate
from ..repository.templates_repository import NotificationsTemplatesRepository
from .renderer import NotificationsRenderer


@dataclass(frozen=True)
class JinjaNotificationsRenderer(NotificationsRenderer):
    repository: NotificationsTemplatesRepository

    def preview_template(
        self,
        template: NotificationsTemplate,
        context: dict[str, Any],
    ) -> NotificationTemplatePreview:
        content = {}
        for render_part in template.parts:
            jinja_template = self.repository.get_jinja_template(template, render_part)

            content[render_part] = jinja_template.render(context)

        return NotificationTemplatePreview(
            template_ref=template.ref,
            content=for_channel(template.ref.channel)(**content),
        )
