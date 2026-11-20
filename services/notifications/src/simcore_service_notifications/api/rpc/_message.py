from celery_library.errors import TaskOrGroupNotFoundError
from fastapi import FastAPI
from models_library.notifications.errors import (
    NotificationsProductNotFoundError,
    NotificationsProductSMTPSettingsNotFoundError,
    NotificationsProductTwilioSettingsNotFoundError,
    NotificationsTaskNotFoundError,
    NotificationsTemplateContextValidationError,
    NotificationsTemplateNotFoundError,
    NotificationsTooManyRecipientsError,
)
from models_library.notifications.rpc import (
    GetMessageStatusRequest,
    GetMessageStatusResponse,
    SendMessageFromTemplateRequest,
    SendMessageRequest,
    SendMessageResponse,
)
from servicelib.rabbitmq import RPCRouter

from ...clients.celery import get_task_manager
from ...models.template import TemplateRef
from .dependencies import get_message_service

router = RPCRouter()


@router.expose(
    reraise_if_error_type=(
        NotificationsProductNotFoundError,
        NotificationsProductSMTPSettingsNotFoundError,
        NotificationsProductTwilioSettingsNotFoundError,
        NotificationsTooManyRecipientsError,
    )
)
async def send_message(
    app: FastAPI,
    *,
    request: SendMessageRequest,
) -> SendMessageResponse:
    assert app  # nosec

    message_service = get_message_service(app)
    task_or_group_uuid, task_name = await message_service.send_message(
        product_name=request.product_name,
        message=request.message,
        owner_metadata=request.owner_metadata,
    )
    return SendMessageResponse(task_or_group_uuid=task_or_group_uuid, task_name=task_name)


@router.expose(
    reraise_if_error_type=(
        NotificationsProductNotFoundError,
        NotificationsProductSMTPSettingsNotFoundError,
        NotificationsProductTwilioSettingsNotFoundError,
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
        product_name=request.product_name,
        addressing=request.addressing,
        ref=TemplateRef(**request.template_ref.model_dump()),
        context=request.context,
        locale=request.locale,
        owner_metadata=request.owner_metadata,
    )
    return SendMessageResponse(task_or_group_uuid=task_or_group_uuid, task_name=task_name)


@router.expose(reraise_if_error_type=(NotificationsTaskNotFoundError,))
async def get_message_status(
    app: FastAPI,
    *,
    request: GetMessageStatusRequest,
) -> GetMessageStatusResponse:
    assert app  # nosec

    task_manager = get_task_manager(app)
    try:
        status = await task_manager.get_status(request.owner_metadata, request.task_or_group_uuid)
    except TaskOrGroupNotFoundError as exc:
        raise NotificationsTaskNotFoundError(task_or_group_uuid=request.task_or_group_uuid) from exc
    return GetMessageStatusResponse(status=status)
