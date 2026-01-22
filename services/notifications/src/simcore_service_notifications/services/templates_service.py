from dataclasses import dataclass
from typing import Any

from ..exceptions.errors import TemplateNotFoundError
from ..models.channel import ChannelType
from ..models.preview import NotificationPreview
from ..models.template import NotificationTemplate, TemplateRef
from ..renderers.renderer import NotificationsRenderer
from ..repository import NotificationsTemplatesRepository


@dataclass(frozen=True)
class NotificationsTemplatesService:
    repository: NotificationsTemplatesRepository
    renderer: NotificationsRenderer

    def list_templates(self, channel: ChannelType) -> list[NotificationTemplate]:
        return self.repository.search_templates(channel=channel)

    def render_preview(self, template_ref: TemplateRef, variables: dict[str, Any]) -> NotificationPreview:
        templates = self.repository.search_templates(
            channel=template_ref.channel,
            template_name=template_ref.template_name,
        )

        if not templates:
            raise TemplateNotFoundError(template_ref=template_ref)

        template = templates[0]

        # validates incoming variables against the template's variables model
        validated_variables = template.variables_model.model_validate(variables)

        return self.renderer.render_preview(
            template=template,
            variables=validated_variables.model_dump(),
        )
