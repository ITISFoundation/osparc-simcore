from enum import auto
from typing import Annotated

from pydantic import Field

from ..utils.enums import StrAutoEnum


class Channel(StrAutoEnum):
    """Defines the supported notification channels.
    This is used to route messages to the appropriate handlers and templates.
    """

    EMAIL = auto()
    SMS = auto()


type TemplateName = Annotated[str, Field(min_length=1)]
