from typing import Literal

from pydantic import BaseModel


class EmailAddress(BaseModel):
    display_name: str | None = None
    addr_spec: str


class EmailChannel(BaseModel):
    type: Literal["email"] = "email"

    from_addr: EmailAddress
    to_addr: EmailAddress
    reply_to_addr: EmailAddress | None = None
