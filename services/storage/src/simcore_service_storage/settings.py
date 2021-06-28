import logging
from typing import List, Optional

from models_library.basic_types import LogLevel, PortInt
from models_library.settings.base import BaseCustomSettings
from models_library.settings.postgres import PostgresSettings
from models_library.settings.s3 import S3Config
from pydantic import Field, PositiveInt
from servicelib.tracing import TracingSettings


class Settings(BaseCustomSettings):

    STORAGE_HOST: str = "0.0.0.0"  # nosec
    STORAGE_PORT: PortInt = 8080

    STORAGE_LOG_LEVEL: LogLevel = Field(
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
        None, description="Blackfynn API key ONLY for testing purposes"
    )
    BF_API_SECRET: Optional[str] = Field(
        None, description="Blackfynn API secret ONLY for testing purposes"
    )

    STORAGE_POSTGRES: PostgresSettings

    STORAGE_S3: S3Config

    STORAGE_TRACING: TracingSettings

    # ----

    @classmethod
    def create_from_envs(cls) -> "Settings":
        cls.set_defaults_with_default_constructors(
            [
                ("STORAGE_POSTGRES", PostgresSettings),
                ("STORAGE_S3", S3Config),
                ("STORAGE_TRACING", TracingSettings),
            ]
        )
        return cls()

    @property
    def logging_level(self) -> int:
        return getattr(logging, self.STORAGE_LOG_LEVEL)
