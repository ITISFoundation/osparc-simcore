from typing import Annotated

from pydantic import BaseModel, Field

from .content import EmailNotificationContent


class EmailAddress(BaseModel):
    name: str
    email: str


class EmailNotificationMessage(BaseModel):
    from_: Annotated[EmailAddress, Field(alias="from")]
    to: Annotated[list[EmailAddress], Field(min_length=1)]

    content: EmailNotificationContent
