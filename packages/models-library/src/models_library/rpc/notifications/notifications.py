from typing import Annotated, Any, Literal, TypeAlias

from pydantic import BaseModel, Field


class _BaseRecipient(BaseModel):
    type: str


class SMSRecipient(_BaseRecipient):
    type: Literal["sms"]
    phone_number: str


class EmailRecipient(_BaseRecipient):
    type: Literal["email"]
    address: str


Recipient: TypeAlias = Annotated[
    EmailRecipient | SMSRecipient, Field(discriminator="type")
]


class NotificationMessage(BaseModel):
    event: str
    context: dict[str, Any] | None = None
