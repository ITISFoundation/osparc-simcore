from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from models_library.celery import GroupUUID, TaskUUID
from models_library.notifications import TemplateRef


class SendMessageRequest(BaseModel):
    message: dict[str, Any]

    model_config = ConfigDict(frozen=True)


class EmailContact(BaseModel):
    name: str | None = None
    email: EmailStr

    model_config = ConfigDict(frozen=True)


class EmailEnvelope(BaseModel):
    from_: Annotated[EmailContact, Field(alias="from")]
    to: list[EmailContact]
    reply_to: EmailContact | None = None
    cc: list[EmailContact] | None = None
    bcc: list[EmailContact] | None = None

    model_config = ConfigDict(
        frozen=True,
        populate_by_name=True,
    )


class SendMessageFromTemplateRequest(BaseModel):
    template_ref: TemplateRef
    context: dict[str, Any]
    envelope: EmailEnvelope

    model_config = ConfigDict(frozen=True)


class SendMessageResponse(BaseModel):
    task_or_group_uuid: TaskUUID | GroupUUID
    task_name: str

    model_config = ConfigDict(frozen=True)
