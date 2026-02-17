import logging
from dataclasses import dataclass
from typing import Any

from models_library.notifications_errors import (
    NotificationsTemplateContextValidationError,
    NotificationsTemplateNotFoundError,
)
from pydantic import ValidationError

from ..models.preview import TemplatePreview
from ..models.template import Template, TemplateRef
from ..renderers.renderer import Renderer
from ..repository import FileTemplatesRepository

_logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TemplatesService:
    templates_repo: FileTemplatesRepository
    renderer: Renderer

    def preview_template(self, ref: TemplateRef, context: dict[str, Any]) -> TemplatePreview:
        templates = self.templates_repo.search_templates(
            channel=ref.channel,
            template_name=ref.template_name,
        )

        if not templates:
            raise NotificationsTemplateNotFoundError(channel=ref.channel, template_name=ref.template_name)

        template = templates[0]

        try:
            # validates incoming variables against the template's variables model
            validated_context = template.context_model.model_validate(context)
        except ValidationError as e:
            _logger.warning(
                "Context validation error for template %s with context %s: %s",
                ref,
                context,
                e,
            )
            raise NotificationsTemplateContextValidationError(
                template_name=ref.template_name,
                channel=ref.channel,
            ) from e

        return self.renderer.preview_template(
            template=template,
            context=validated_context.model_dump(),
        )

    def search_templates(self, channel: str | None, template_name: str | None) -> list[Template]:
        return self.templates_repo.search_templates(channel=channel, template_name=template_name)
