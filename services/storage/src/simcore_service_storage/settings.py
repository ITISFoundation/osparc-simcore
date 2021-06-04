""" Configuration of simcore_service_storage

The application can consume settings revealed at different
stages of the development workflow. This submodule gives access
to all of them.


Naming convention:

APP_*_KEY: is a key in app-storage
RQT_*_KEY: is a key in request-storage
RSP_*_KEY: is a key in response-storage

See https://docs.aiohttp.org/en/stable/web_advanced.html#data-sharing-aka-no-singletons-please
"""

from typing import Any, Dict, List, Optional

from models_library.basic_types import LogLevel
from models_library.settings.application_bases import BaseAiohttpAppSettings
from models_library.settings.postgres import PostgresSettings
from models_library.settings.s3 import S3Config
from pydantic import BaseSettings, Field, SecretStr
from servicelib.tracing import TracingSettings


class BfApiToken(BaseSettings):
    token_key: str = Field(..., env="BF_API_KEY")
    token_secret: str = Field(..., env="BF_API_SECRET")


def create_settings_class():
    class Settings(BaseAiohttpAppSettings):
        # GENERAL SETTINGS ---

        loglevel: LogLevel = Field(
            "INFO", env=["STORAGE_LOGLEVEL", "LOG_LEVEL", "LOGLEVEL"]
        )

        testing: bool = False
        max_workers: int = 8
        monitoring_enabled: bool = False
        test_datcore: Optional[BfApiToken] = None
        disable_services: List[str] = []

        # APP MODULES SETTINGS ----

        postgres: PostgresSettings = PostgresSettings()

        s3: S3Config = S3Config()

        rest: Dict[str, Any] = {"enabled": True}

        tracing: TracingSettings = TracingSettings()

        class Config:
            case_sensitive = False
            env_prefix = "STORAGE_"
            json_encoders = {SecretStr: lambda v: v.get_secret_value()}

    return Settings
