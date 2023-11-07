from typing import Final

from pydantic import Field, NonNegativeInt, PositiveFloat
from settings_library.base import BaseCustomSettings

_MINUTE: Final[NonNegativeInt] = 60


class DynamicServicesSchedulerSettings(BaseCustomSettings):
    DIRECTOR_V2_DYNAMIC_SCHEDULER_ENABLED: bool = True

    DIRECTOR_V2_DYNAMIC_SCHEDULER_INTERVAL_SECONDS: PositiveFloat = Field(
        5.0, description="interval at which the scheduler cycle is repeated"
    )

    DIRECTOR_V2_DYNAMIC_SCHEDULER_PENDING_VOLUME_REMOVAL_INTERVAL_S: PositiveFloat = (
        Field(
            30 * _MINUTE,
            description="interval at which cleaning of unused dy-sidecar "
            "docker volume removal services is executed",
        )
    )
