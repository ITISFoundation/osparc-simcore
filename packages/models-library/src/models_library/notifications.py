from enum import StrEnum
from typing import Annotated

from pydantic import Field


class ChannelType(StrEnum):
    email = "email"


type TemplateName = Annotated[str, Field(min_length=1)]
