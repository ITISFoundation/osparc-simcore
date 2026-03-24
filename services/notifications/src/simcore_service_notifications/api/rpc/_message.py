from fastapi import FastAPI
from models_library.notifications.errors import (
    NotificationsTemplateContextValidationError,
    NotificationsTemplateNotFoundError,
    NotificationsTooManyRecipientsError,
)
from models_library.notifications.rpc import (
    SendMessageFromTemplateRequest,
    SendMessageRequest,
    SendMessageResponse,
)
from servicelib.rabbitmq import RPCRouter

from ...models.template import TemplateRef
from .dependencies import get_message_service

router = RPCRouter()


@router.expose(reraise_if_error_type=(NotificationsTooManyRecipientsError,))
async def send_message(
    app: FastAPI,
    *,
    request: SendMessageRequest,
) -> SendMessageResponse:
    assert app  # nosec

    message_service = get_message_service(app)
    task_or_group_uuid, task_name = await message_service.send_message(
        message=request.message,
        owner_metadata=request.owner_metadata,
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

    message_service = get_message_service(app)
    task_or_group_uuid, task_name = await message_service.send_message_from_template(
        addressing=request.addressing,
        ref=TemplateRef(**request.template_ref.model_dump()),
        context=request.context,
        owner_metadata=request.owner_metadata,
    )
    return SendMessageResponse(task_or_group_uuid=task_or_group_uuid, task_name=task_name)
