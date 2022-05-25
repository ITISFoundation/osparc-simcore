from typing import Final

from models_library.basic_types import LogLevel
from pydantic import Field, PositiveFloat, PositiveInt
from settings_library.base import BaseCustomSettings
from settings_library.catalog import CatalogSettings

_MINUTE: Final[PositiveInt] = 60


class ImagePullerSettings(BaseCustomSettings):
    IMAGE_PULLER_LOG_LEVEL: LogLevel = Field(LogLevel.INFO.value)

    IMAGE_PULLER_CATALOG: CatalogSettings = Field(auto_default_from_env=True)
    IMAGE_PULLER_CATALOG_REQUEST_TIMEOUT: PositiveFloat = 30.0

    IMAGE_PULLER_CHECK_INTERVAL_S: PositiveInt = Field(
        30 * _MINUTE,
        description=(
            "time to wait between each attempt to check the catalog "
            "for new images to sync"
        ),
    )

    IMAGE_PULLER_CHECK_HOSTNAME: str = Field(
        ...,
        env=["HOSTNAME", "IMAGE_PULLER_CHECK_HOSTNAME"],
        description="Used to uniquely identify the requesting client",
    )
