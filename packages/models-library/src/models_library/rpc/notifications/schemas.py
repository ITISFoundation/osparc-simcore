from typing import Annotated, Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, EmailStr, Field
from pydantic_extra_types.phone_numbers import PhoneNumber


class Event(BaseModel):
    type: str

    model_config = ConfigDict(
        frozen=True,
    )


class EmailChannel(BaseModel):
    type: Literal["email"] = "email"

    to: EmailStr
    reply_to: EmailStr | None = None


class SMSChannel(BaseModel):
    type: Literal["sms"] = "sms"

    phone_number: PhoneNumber


Channel: TypeAlias = EmailChannel | SMSChannel


class Notification(BaseModel):
    event: Event
    channel: Annotated[Channel, Field(discriminator="type")]
