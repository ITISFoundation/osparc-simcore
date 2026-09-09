from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from .. import Channel

type PhoneNumberStr = Annotated[
    str,
    # SEE https://en.wikipedia.org/wiki/E.164
    StringConstraints(pattern=r"^\+[1-9]\d{6,14}$"),
]


class SmsContact(BaseModel):
    phone_number: PhoneNumberStr


class SmsContent(BaseModel):
    body: Annotated[
        str,
        # NOTE: a single SMS segment is 160 chars (GSM-7) or 70 chars (UCS-2, e.g. non-latin alphabets)
        Field(min_length=1, max_length=1600),
    ]


class SmsAddressing(BaseModel):
    to: list[SmsContact]

    model_config = ConfigDict(
        frozen=True,
    )


class SmsMessage(BaseModel):
    channel: Literal[Channel.sms] = Channel.sms

    addressing: SmsAddressing
    content: SmsContent
