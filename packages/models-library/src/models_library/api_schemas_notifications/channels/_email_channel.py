from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class EmailAddress(BaseModel):
    display_name: str = ""
    addr_spec: EmailStr


class EmailAttachment(BaseModel):
    filename: str
    content: bytes


class EmailChannel(BaseModel):
    type: Literal["email"] = "email"

    from_: Annotated[EmailAddress, Field(alias="from")]
    to: EmailAddress
    reply_to: EmailAddress | None = None
    attachments: list[EmailAttachment] | None = None

    model_config = ConfigDict(
        validate_by_alias=True,
        validate_by_name=True,
    )
