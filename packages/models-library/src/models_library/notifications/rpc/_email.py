from typing import Annotated

from pydantic import BaseModel, EmailStr, Field

from .. import Channel


class EmailContact(BaseModel):
    name: str
    email: EmailStr


class EmailMessageContent(BaseModel):
    subject: Annotated[str, Field(min_length=1, max_length=998)]
    body_html: str | None = None
    body_text: str | None = None


class Message(BaseModel):
    channel: Channel


class EmailEnvelope(Message):
    channel: Channel = Channel.email
    from_: Annotated[EmailContact, Field(alias="from")]
    to: list[EmailContact]


class EmailMessage(EmailEnvelope):
    channel: Channel = Channel.email
    content: EmailMessageContent
