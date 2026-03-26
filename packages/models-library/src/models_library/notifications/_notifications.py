from enum import StrEnum
from typing import Annotated

from pydantic import Field


class Channel(StrEnum):
    """Defines the supported notification channels.
    This is used to route messages to the appropriate handlers and templates.
    """

    email = "email"


type TemplateName = Annotated[str, Field(min_length=1)]
