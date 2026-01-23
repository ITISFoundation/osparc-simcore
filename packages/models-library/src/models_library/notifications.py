from enum import StrEnum
from typing import Annotated

from pydantic import Field


class ChannelType(StrEnum):
    email = "email"
    sms = "sms"


type TemplateName = Annotated[str, Field(min_length=1)]
