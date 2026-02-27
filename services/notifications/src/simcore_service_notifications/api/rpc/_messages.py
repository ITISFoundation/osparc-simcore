from fastapi import FastAPI
from models_library.notifications.rpc import (
    SendMessageFromTemplateRequest,
)
from servicelib.celery.async_jobs.notifications import submit_send_message_task
from servicelib.rabbitmq import RPCRouter

from ...api.rpc.dependencies import get_templates_service
from ...clients.celery import get_task_manager
from ...models.template import TemplateRef
from ...modules.celery._models import NotificationsOwnerMetadata

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
    channel = request.ref.channel

    await submit_send_message_task(
        get_task_manager(app),
        owner_metadata=NotificationsOwnerMetadata(),
        channel=channel,
        message={
            # NOTE: validated internally
            "envelope": request.envelope.model_dump(),
            "content": template_preview.message_content.model_dump(),
        },
    )
