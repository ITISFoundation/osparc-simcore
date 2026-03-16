from fastapi import FastAPI
from models_library.notifications.rpc import (
    SendMessageRequest,
    SendMessageResponse,
)
from servicelib.rabbitmq import RPCRouter

from .dependencies import get_messages_service

router = RPCRouter()


@router.expose()
async def send_message(
    app: FastAPI,
    *,
    request: SendMessageRequest,
) -> SendMessageResponse:
    assert app  # nosec

    messages_service = get_messages_service(app)
    task_or_group_uuid, task_name = await messages_service.send_message(
        message=request.message,
    )
    return SendMessageResponse(task_or_group_uuid=task_or_group_uuid, task_name=task_name)


@router.expose()
async def send_message_from_template(
    app: FastAPI,
    *,
    request: SendMessageRequest,
) -> SendMessageResponse:
    assert app  # nosec

    messages_service = get_messages_service(app)
    task_or_group_uuid, task_name = await messages_service.send_message(
        message=request.message,
    )
    return SendMessageResponse(task_or_group_uuid=task_or_group_uuid, task_name=task_name)
