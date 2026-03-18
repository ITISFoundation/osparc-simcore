from typing import Annotated

from pydantic import BaseModel, EmailStr, Field

from .. import Channel


class EmailContact(BaseModel):
    name: str
    email: EmailStr


class EmailContent(BaseModel):
    subject: Annotated[str, Field(min_length=1, max_length=998)]
    body_html: str | None = None
    body_text: str | None = None


class EmailEnvelope(BaseModel):
    from_: Annotated[EmailContact, Field(alias="from")]
    to: list[EmailContact]


class EmailMessage(BaseModel):
    channel: Channel = Channel.email

    envelope: EmailEnvelope
    content: EmailContent


type Envelope = EmailEnvelope
type Message = EmailMessage
