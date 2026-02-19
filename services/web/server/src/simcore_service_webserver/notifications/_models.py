from email.utils import parseaddr
from typing import Annotated, Self

from common_library.network import replace_email_parts
from models_library.notifications import ChannelType
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class EmailContact(BaseModel):
    name: str = ""
    email: EmailStr

    @classmethod
    def from_email_str(cls, email_str: str) -> Self:
        name, email = parseaddr(email_str)
        return cls(name=name, email=email)

    def to_email_str(self) -> str:
        if self.name:
            return f"{self.name} <{self.email}>"
        return self.email

    def replace(
        self,
        new_name: str | None = None,
        new_local: str | None = None,
    ) -> Self:
        """Replace the local part and/or display name of the email address.

        Args:
            new_local: New local part (before @). If None, keeps current.
            new_name: Optional custom display name. If None and new_local is provided,
              auto-generates from new_local if original had a display name.

        Returns:
            New EmailContact instance with updated values
        """
        if new_local is None:
            # Only update name if provided, otherwise return copy as-is
            if new_name is not None:
                return self.model_copy(update={"name": new_name})
            return self

        new_email = replace_email_parts(
            self.to_email_str(),
            new_local,
            new_name,
        )

        return type(self).from_email_str(new_email)

    model_config = ConfigDict(
        frozen=True,
    )


class EmailAttachment(BaseModel):
    content: bytes
    filename: str

    model_config = ConfigDict(
        frozen=True,
    )


class EmailContent(BaseModel):
    subject: str
    body_text: str
    body_html: str | None = None

    model_config = ConfigDict(
        frozen=True,
    )


class EmailMessage(BaseModel):
    channel: ChannelType = ChannelType.email

    from_: Annotated[EmailContact, Field(alias="from")]
    to: list[EmailContact]
    reply_to: EmailContact | None = None
    bcc: list[EmailContact] | None = None

    content: EmailContent

    attachments: list[EmailAttachment] | None = None

    model_config = ConfigDict(
        frozen=True,
        validate_by_alias=True,
        validate_by_name=True,
    )


type Contact = EmailContact
type Message = EmailMessage
