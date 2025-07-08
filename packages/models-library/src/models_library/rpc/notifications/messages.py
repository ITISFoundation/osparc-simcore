from abc import ABC
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr


class Channel(BaseModel, ABC):
    type: str

    model_config = ConfigDict(
        frozen=True,
    )


class EmailChannel(Channel):
    type: Literal["email"] = "email"
    to: EmailStr
    reply_to: EmailStr | None = None


class SMSChannel(Channel):
    type: Literal["sms"] = "sms"
    phone_number: str  # Consider using phone number validation library here


class NotificationMessage(BaseModel):
    event_type: str  # e.g. "account.registered"
    channel: Channel
    context: dict[str, Any] | None = None  # Additional context for the notification
