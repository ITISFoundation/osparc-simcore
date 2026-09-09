"""Celery worker task payloads for notifications service."""

from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints

from .. import Channel

type PhoneNumberStr = Annotated[
    str,
    # NOTE: E.164 format
    StringConstraints(pattern=r"^\+[1-9]\d{6,14}$"),
]


class SmsContact(BaseModel):
    phone_number: PhoneNumberStr


class SmsMessage(BaseModel):
    channel: Literal[Channel.sms] = Channel.sms

    to: SmsContact
    body: Annotated[str, Field(min_length=1, max_length=1600)]
