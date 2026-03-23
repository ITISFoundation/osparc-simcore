from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from .. import Channel


class EmailContact(BaseModel):
    name: str
    email: EmailStr


class EmailContent(BaseModel):
    subject: Annotated[str, Field(min_length=1, max_length=998)]
    body_html: str | None = None
    body_text: str | None = None


class EmailAddressing(BaseModel):
    from_: Annotated[EmailContact, Field(alias="from")]
    to: list[EmailContact]

    model_config = ConfigDict(
        frozen=True,
        validate_by_alias=True,
        validate_by_name=True,
    )


class EmailMessage(BaseModel):
    channel: Channel = Channel.email

    addressing: EmailAddressing
    content: EmailContent


type Addressing = EmailAddressing
type Message = EmailMessage
