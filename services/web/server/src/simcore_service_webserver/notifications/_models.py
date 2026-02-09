from email.utils import parseaddr
from typing import Annotated, Self

from common_library.network import replace_email_parts
from models_library.emails import LowerCaseEmailStr
from models_library.notifications import ChannelType
from pydantic import BaseModel, ConfigDict, Field


class EmailAddress(BaseModel):
    display_name: str = ""
    addr_spec: LowerCaseEmailStr

    @classmethod
    def from_email_str(cls, email_str: str) -> Self:
        display_name, addr_spec = parseaddr(email_str)
        return cls(display_name=display_name, addr_spec=addr_spec)

    def to_email_str(self) -> str:
        if self.display_name:
            return f"{self.display_name} <{self.addr_spec}>"
        return self.addr_spec

    def replace(
        self,
        new_display_name: str | None = None,
        new_addr_local: str | None = None,
    ) -> Self:
        """Replace the local part and/or display name of the email address.

        Args:
            new_addr_local: New local part (before @). If None, keeps current.
            new_display_name: Optional custom display name. If None and new_addr_local is provided,
              auto-generates from new_addr_local if original had a display name.

        Returns:
            New EmailAddress instance with updated values
        """
        if new_addr_local is None:
            # Only update display_name if provided, otherwise return copy as-is
            if new_display_name is not None:
                return self.model_copy(update={"display_name": new_display_name})
            return self

        transformed_email = replace_email_parts(
            self.to_email_str(),
            new_addr_local,
            new_display_name,
        )

        return type(self).from_email_str(transformed_email)

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


class EmailNotificationMessage(BaseModel):
    channel: ChannelType = ChannelType.email

    from_: Annotated[EmailAddress, Field(alias="from")]
    to: list[EmailAddress] | None = None
    reply_to: EmailAddress | None = None
    bcc: list[EmailAddress] | None = None

    content: EmailContent

    attachments: list[EmailAttachment] | None = None

    model_config = ConfigDict(
        frozen=True,
        validate_by_alias=True,
        validate_by_name=True,
    )
