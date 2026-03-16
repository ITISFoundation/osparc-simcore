from typing import Any

from pydantic import BaseModel, ConfigDict

from models_library.celery import GroupUUID, TaskUUID
from models_library.notifications import TemplateRef


class SendMessageRequest(BaseModel):
    message: dict[str, Any]

    model_config = ConfigDict(frozen=True)


class SendMessageFromTemplateRequest(BaseModel):
    template_ref: TemplateRef
    context: dict[str, Any]

    # GCR: add envelope here!

    model_config = ConfigDict(frozen=True)


class SendMessageResponse(BaseModel):
    task_or_group_uuid: TaskUUID | GroupUUID
    task_name: str

    model_config = ConfigDict(frozen=True)
