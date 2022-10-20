from typing import Final

from pydantic import Field, NonNegativeInt
from settings_library.base import BaseCustomSettings

_MIN: Final[NonNegativeInt] = 60


class ApplicationSettings(BaseCustomSettings):
    SIMCORE_AGENT_INTERVAL_VOLUMES_CLEANUP_S: NonNegativeInt = Field(
        60 * _MIN, description="interval at which to repeat volumes cleanup"
    )
