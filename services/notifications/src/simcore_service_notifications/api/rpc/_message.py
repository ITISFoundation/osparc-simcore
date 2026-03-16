from fastapi import FastAPI
from models_library.notifications.errors import (
    NotificationsTemplateContextValidationError,
    NotificationsTemplateNotFoundError,
)
from models_library.notifications.rpc import (
    SendMessageFromTemplateRequest,
    SendMessageRequest,
    SendMessageResponse,
)
from servicelib.rabbitmq import RPCRouter

from ...models.template import TemplateRef
from .dependencies import get_message_service, get_template_service

router = RPCRouter()


@router.expose()
async def send_message(
    app: FastAPI,
    *,
    request: SendMessageRequest,
) -> SendMessageResponse:
    assert app  # nosec

    messages_service = get_message_service(app)
    task_or_group_uuid, task_name = await messages_service.send_message(
        message=request.message,
    )
    return SendMessageResponse(task_or_group_uuid=task_or_group_uuid, task_name=task_name)


@router.expose(
    reraise_if_error_type=(
        NotificationsTemplateNotFoundError,
        NotificationsTemplateContextValidationError,
    )
)
async def send_message_from_template(
    app: FastAPI,
    *,
    request: SendMessageFromTemplateRequest,
) -> SendMessageResponse:
    assert app  # nosec

    template_service = get_template_service()
    preview = template_service.preview_template(
        ref=TemplateRef(**request.template_ref.model_dump()),
        context=request.context,
    )

    envelope_data = request.envelope.model_dump(by_alias=True)
    message = {
        "channel": request.template_ref.channel,
        **envelope_data,
        "content": preview.message_content.model_dump()
        if hasattr(preview.message_content, "model_dump")
        else preview.message_content,
    }

    messages_service = get_message_service(app)
    task_or_group_uuid, task_name = await messages_service.send_message(
        message=message,
    )
    return SendMessageResponse(task_or_group_uuid=task_or_group_uuid, task_name=task_name)
