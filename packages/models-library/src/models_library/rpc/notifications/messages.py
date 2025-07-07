from abc import ABC
from typing import Annotated, Any, TypeAlias

from pydantic import BaseModel, Field


class BaseRecipient(BaseModel, ABC):
    type: str


class SMSRecipient(BaseRecipient):
    type: Annotated[str, Field(frozen=True)] = "sms"
    phone_number: str


class EmailRecipient(BaseRecipient):
    type: Annotated[str, Field(frozen=True)] = "email"
    address: str


Recipient: TypeAlias = Annotated[
    EmailRecipient | SMSRecipient, Field(discriminator="type")
]


class NotificationMessage(BaseModel):
    event: str
    context: dict[str, Any] | None = None
