from typing import Annotated

from pydantic import BaseModel, EmailStr, Field


class EmailContact(BaseModel):
    name: str | None = None
    email: EmailStr


class EmailAttachment(BaseModel):
    content: bytes
    filename: str


class EmailEnvelope(BaseModel):
    from_: Annotated[EmailContact, Field(alias="from")]
    to: EmailContact
    cc: EmailContact | None = None
    bcc: EmailContact | None = None

    attachments: list[EmailAttachment] | None = None
