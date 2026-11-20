from enum import StrEnum
from typing import Annotated

from pydantic import Field, StringConstraints


class Channel(StrEnum):
    """Defines the supported notification channels.
    This is used to route messages to the appropriate handlers and templates.
    """

    email = "email"
    sms = "sms"


type TemplateName = Annotated[str, Field(min_length=1)]

type PhoneNumberStr = Annotated[
    str,
    # SEE https://en.wikipedia.org/wiki/E.164
    # the web-server accepts looser user input and normalizes it to this format
    # before publishing (PhoneNumberValidator), see simcore_service_webserver/models.py
    StringConstraints(pattern=r"^\+[1-9]\d{6,14}$"),
]
