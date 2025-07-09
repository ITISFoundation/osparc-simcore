from typing import Literal

from pydantic import BaseModel, EmailStr


class EmailAddress(BaseModel):
    display_name: str | None = None
    addr_spec: EmailStr


class EmailChannel(BaseModel):
    type: Literal["email"] = "email"

    from_addr: EmailAddress
    to_addr: EmailAddress
    reply_to_addr: EmailAddress | None = None
