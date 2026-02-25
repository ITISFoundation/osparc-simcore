from fastapi import FastAPI
from models_library.notifications.rpc import (
    SendMessageFromTemplateRequest,
)
from servicelib.rabbitmq import RPCRouter

from ...api.rpc.dependencies import get_templates_service
from ...models.template import TemplateRef

router = RPCRouter()


@router.expose()
async def send_message_from_template(
    app: FastAPI,
    *,
    request: SendMessageFromTemplateRequest,
) -> None:
    assert app  # nosec

    template_service = get_templates_service()
    template_preview = template_service.preview_template(
        ref=TemplateRef(**request.ref.model_dump()),
        context=request.template_context,
    )
    assert template_preview  # nosec

    raise NotImplementedError
