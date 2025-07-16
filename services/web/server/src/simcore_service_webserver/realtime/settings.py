from typing import Annotated

from pydantic import (
    PositiveInt,
)
from pydantic.fields import Field
from settings_library.base import BaseCustomSettings


class RealTimeCollaborationSettings(BaseCustomSettings):
    RTC_MAX_NUMBER_OF_USERS: Annotated[
        PositiveInt,
        Field(
            description="Maximum number of users allowed in a real-time collaboration session",
        ),
    ]
