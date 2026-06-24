import logging
from dataclasses import asdict, dataclass
from typing import Any

from models_library.notifications.errors import (
    NotificationsTemplateContextValidationError,
    NotificationsTemplateNotFoundError,
)
from models_library.products import ProductName
from pydantic import ValidationError

from ..models.template import Template, TemplatePreview, TemplateRef
from ..renderers import Renderer
from ..repositories.product import ProductRepository
from ..repositories.template import TemplateRepository

_logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TemplateService:
    repository: TemplateRepository
    renderer: Renderer
    product_repository: ProductRepository

    async def preview_template(
        self,
        product_name: ProductName,
        ref: TemplateRef,
        context: dict[str, Any],
        locale: str = "en",
    ) -> TemplatePreview:
        product_data = await self.product_repository.get_product(product_name)
        context_with_product = {**context, "product": asdict(product_data)}

        templates = self.repository.search_templates(
            channel=ref.channel,
            template_name=ref.template_name,
        )

        if not templates:
            raise NotificationsTemplateNotFoundError(channel=ref.channel, template_name=ref.template_name)

        template = templates[0]

        try:
            # validates incoming variables against the template's variables model
            validated_context = template.context_model.model_validate(context_with_product)
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
            locale=locale,
        )

    def search_templates(self, channel: str | None, template_name: str | None) -> list[Template]:
        return self.repository.search_templates(channel=channel, template_name=template_name)
