import logging
import os
from typing import List, Optional

from models_library.basic_types import LogLevel, PortInt
from models_library.settings.postgres import PostgresSettings
from models_library.settings.s3 import S3Config
from pydantic import BaseSettings, Field, PositiveInt, SecretStr
from servicelib.tracing import TracingSettings


class Settings(BaseSettings):

    STORAGE_HOST: str = "0.0.0.0"  # nosec
    STORAGE_PORT: PortInt = 8080

    STORAGE_LOG_LEVEL: LogLevel = Field(
        "INFO", env=["STORAGE_LOGLEVEL", "LOG_LEVEL", "LOGLEVEL"]
    )

    STORAGE_MAX_WORKERS: PositiveInt = Field(
        8, description="Number of workers for the thead executor pool"
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

    class Config:
        json_encoders = {SecretStr: lambda v: v.get_secret_value()}

    @classmethod
    def create_from_env(cls) -> "Settings":
        # NOTE: This control when defaults of sub-sections
        # are created

        defaults = {}
        for name, default_cls in [
            ("STORAGE_POSTGRES", PostgresSettings),
            ("STORAGE_S3", S3Config),
            ("STORAGE_TRACING", TracingSettings),
        ]:
            if name not in os.environ:
                defaults[name] = default_cls()
        return cls(**defaults)

    @property
    def logging_level(self) -> int:
        return getattr(logging, self.STORAGE_LOG_LEVEL)
