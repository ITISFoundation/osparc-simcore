"""Celery worker task payloads for notifications service."""

from typing import Annotated, Literal

from pydantic import BaseModel, Field

from .._notifications import Channel, PhoneNumberStr


class SmsContact(BaseModel):
    phone_number: PhoneNumberStr


class SmsMessage(BaseModel):
    channel: Literal[Channel.sms] = Channel.sms

    to: SmsContact
    body: Annotated[str, Field(min_length=1, max_length=1600)]
