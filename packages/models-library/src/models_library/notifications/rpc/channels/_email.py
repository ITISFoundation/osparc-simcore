from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class EmailContact(BaseModel):
    name: str | None = None
    email: EmailStr

    model_config = ConfigDict(
        frozen=True,
    )


class EmailAttachment(BaseModel):
    content: bytes
    filename: str

    model_config = ConfigDict(
        frozen=True,
    )


class EmailEnvelope(BaseModel):
    from_: Annotated[EmailContact, Field(alias="from")]
    to: EmailContact
    cc: EmailContact | None = None
    bcc: EmailContact | None = None

    attachments: list[EmailAttachment] | None = None

    model_config = ConfigDict(
        frozen=True,
        validate_by_name=True,
    )
