from abc import ABC
from typing import Annotated, Any, Literal, TypeAlias

from pydantic import BaseModel, Field


class BaseRecipient(BaseModel, ABC):
    type: str


class SMSRecipient(BaseRecipient):
    type: Literal["sms"]
    phone_number: str


class EmailRecipient(BaseRecipient):
    type: Literal["email"]
    address: str


Recipient: TypeAlias = Annotated[
    EmailRecipient | SMSRecipient, Field(discriminator="type")
]


class NotificationMessage(BaseModel):
    event: str
    context: dict[str, Any] | None = None
