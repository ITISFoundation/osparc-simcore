from dataclasses import dataclass
from typing import Any

from ..models.preview import NotificationPreview
from ..models.template import TemplateRef
from ..renderers.renderer import NotificationsRenderer
from ..repository import NotificationsTemplatesRepository


@dataclass(frozen=True)
class NotificationsTemplatesService:
    repository: NotificationsTemplatesRepository
    renderer: NotificationsRenderer

    def render_preview(self, template_ref: TemplateRef, variables: dict[str, Any]) -> NotificationPreview:
        template = self.repository.get_template(template_ref)

        validated_variables = template.variables_model.model_validate(variables)

        return self.renderer.render_preview(
            template=template,
            variables=validated_variables.model_dump(),
        )
