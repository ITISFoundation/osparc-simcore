from typing import TypeAlias

from ._email_channel import EmailAddress, EmailChannel
from ._sms_channel import SMSChannel

Channel: TypeAlias = EmailChannel | SMSChannel


__all__: tuple[str, ...] = (
    "Channel",
    "EmailAddress",
    "EmailChannel",
    "SMSChannel",
)

# nopycln: file
