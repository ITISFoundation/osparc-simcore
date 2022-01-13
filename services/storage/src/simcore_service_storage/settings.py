from typing import List, Optional

from pydantic import Field, PositiveInt, validator
from settings_library.base import BaseCustomSettings
from settings_library.basic_types import LogLevel, PortInt
from settings_library.logging_utils import MixinLoggingSettings
from settings_library.postgres import PostgresSettings
from settings_library.s3 import S3Settings
from settings_library.tracing import TracingSettings

from .datcore_adapter.datcore_adapter_settings import DatcoreAdapterSettings


class Settings(BaseCustomSettings, MixinLoggingSettings):

    STORAGE_HOST: str = "0.0.0.0"  # nosec
    STORAGE_PORT: PortInt = 8080

    LOG_LEVEL: LogLevel = Field(
        "INFO", env=["STORAGE_LOGLEVEL", "LOG_LEVEL", "LOGLEVEL"]
    )

    STORAGE_MAX_WORKERS: PositiveInt = Field(
        8,
        description="Number of workers for the thead executor pool used in DatcoreWrapper",
    )

    STORAGE_MONITORING_ENABLED: bool = False

    STORAGE_DISABLE_SERVICES: List[str] = []

    STORAGE_TESTING: bool = Field(
        False, description="Flag to enable some fakes for testing purposes"
    )
    BF_API_KEY: Optional[str] = Field(
        None, description="Pennsieve API key ONLY for testing purposes"
    )
    BF_API_SECRET: Optional[str] = Field(
        None, description="Pennsieve API secret ONLY for testing purposes"
    )

    STORAGE_POSTGRES: PostgresSettings

    STORAGE_S3: S3Settings

    STORAGE_TRACING: Optional[TracingSettings]

    DATCORE_ADAPTER: DatcoreAdapterSettings

    STORAGE_SYNC_METADATA_TIMEOUT: PositiveInt = Field(
        180, description="Timeout (seconds) for metadata sync task"
    )

    @validator("LOG_LEVEL")
    @classmethod
    def _validate_loglevel(cls, value) -> str:
        return cls.validate_log_level(value)
