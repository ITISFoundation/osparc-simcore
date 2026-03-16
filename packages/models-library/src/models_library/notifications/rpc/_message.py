from typing import Any

from pydantic import BaseModel, ConfigDict

from ...celery import GroupUUID, TaskUUID
from ._template import TemplateRef


class SendMessageRequest(BaseModel):
    message: dict[str, Any]

    model_config = ConfigDict(frozen=True)


class SendMessageFromTemplateRequest(BaseModel):
    envelope: dict[str, Any]

    # fields used to generate the message content
    template_ref: TemplateRef
    context: dict[str, Any]

    model_config = ConfigDict(frozen=True)


class SendMessageResponse(BaseModel):
    task_or_group_uuid: TaskUUID | GroupUUID
    task_name: str

    model_config = ConfigDict(frozen=True)
