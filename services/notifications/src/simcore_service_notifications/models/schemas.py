from typing import Any, TypeAlias

from pydantic import BaseModel


class SMSRecipient(BaseModel):
    phone_number: str


class EmailRecipient(BaseModel):
    email: str


Recipient: TypeAlias = SMSRecipient | EmailRecipient


class NotificationMessage(BaseModel):
    event: str
    context: dict[str, Any] | None = None
