from dataclasses import asdict

from fastapi import FastAPI
from models_library.notifications import ChannelType
from models_library.notifications.errors import (
    TemplateContextValidationError,
    TemplateNotFoundError,
)
from models_library.notifications.rpc import (
    PreviewTemplateRequest,
    PreviewTemplateResponse,
    SearchTemplatesResponse,
)
from models_library.notifications.rpc import (
    TemplateRef as TemplateRefRpc,
)
from servicelib.rabbitmq import RPCRouter

from ...models.template import TemplateRef
from .dependencies import get_templates_service

router = RPCRouter()


@router.expose(
    reraise_if_error_type=(
        TemplateContextValidationError,
        TemplateNotFoundError,
    )
)
async def preview_template(
    app: FastAPI,
    *,
    request: PreviewTemplateRequest,
) -> PreviewTemplateResponse:
    """Previews a notification template by rendering it with the provided context."""
    assert app  # nosec

    service = get_templates_service()

    preview = service.preview_template(
        ref=TemplateRef(**request.ref.model_dump()),
        context=request.context,
    )

    return PreviewTemplateResponse(
        ref=request.ref,
        message_content=preview.message_content.model_dump(),
    )


@router.expose()
async def search_templates(
    app: FastAPI,
    *,
    channel: ChannelType | None,
    template_name: str | None,
) -> list[SearchTemplatesResponse]:
    """
    Searches for notification templates based on the specified channel and template name.

    Args:
        app: The FastAPI application instance.
        channel: The channel type to filter templates. Use `None` to search across all channels.
        template_name: The name of the template to search for.
            Use wildcards (e.g., `*`, `?`) for partial matches. `None` searches for all templates.

    Returns:
        A list of notification template responses matching the search criteria.
    """
    assert app  # nosec

    templates_service = get_templates_service()
    templates = templates_service.search_templates(channel, template_name)

    return [
        SearchTemplatesResponse(
            ref=TemplateRefRpc(**asdict(template.ref)),
            context_schema=template.context_model.model_json_schema(),
        )
        for template in templates
    ]
