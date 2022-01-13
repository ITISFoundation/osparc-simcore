from functools import cached_property
from typing import Optional

from models_library.basic_types import BootModeEnum, LogLevel
from pydantic import Field, SecretStr
from pydantic.class_validators import validator
from pydantic.networks import HttpUrl
from settings_library.base import BaseCustomSettings
from settings_library.logging_utils import MixinLoggingSettings
from settings_library.postgres import PostgresSettings
from settings_library.tracing import TracingSettings

# SERVICES CLIENTS --------------------------------------------


class _UrlMixin:
    def _build_url(self, prefix: str) -> str:
        prefix = prefix.upper()
        return HttpUrl.build(
            scheme="http",
            host=getattr(self, f"{prefix}_HOST"),
            port=f"{getattr(self, f'{prefix}_PORT')}",
            path=f"/{getattr(self, f'{prefix}_VTAG')}",
        )


class WebServerSettings(BaseCustomSettings, _UrlMixin):
    WEBSERVER_HOST: str = "webserver"
    WEBSERVER_PORT: int = 8080
    WEBSERVER_VTAG: str = "v0"

    WEBSERVER_SESSION_SECRET_KEY: SecretStr
    WEBSERVER_SESSION_NAME: str = "osparc.WEBAPI_SESSION"

    @cached_property
    def base_url(self) -> str:
        return self._build_url("WEBSERVER")


# TODO: dynamically create types with minimal options?
class CatalogSettings(BaseCustomSettings, _UrlMixin):
    CATALOG_HOST: str = "catalog"
    CATALOG_PORT: int = 8000
    CATALOG_VTAG: str = "v0"

    @cached_property
    def base_url(self) -> str:
        return self._build_url("CATALOG")


class StorageSettings(BaseCustomSettings, _UrlMixin):
    STORAGE_HOST: str = "storage"
    STORAGE_PORT: int = 8080
    STORAGE_VTAG: str = "v0"

    @cached_property
    def base_url(self) -> str:
        return self._build_url("STORAGE")


class DirectorV2Settings(BaseCustomSettings, _UrlMixin):
    DIRECTOR_V2_HOST: str = "director-v2"
    DIRECTOR_V2_PORT: int = 8000
    DIRECTOR_V2_VTAG: str = "v2"

    @cached_property
    def base_url(self) -> str:
        return self._build_url("DIRECTOR")


# MAIN SETTINGS --------------------------------------------


class AppSettings(BaseCustomSettings, MixinLoggingSettings):
    # pylint: disable=no-self-use
    # pylint: disable=no-self-argument

    # DOCKER
    SC_BOOT_MODE: Optional[BootModeEnum]

    # LOGGING
    LOG_LEVEL: LogLevel = Field(
        LogLevel.INFO.value,
        env=["API_SERVER_LOGLEVEL", "LOG_LEVEL", "LOGLEVEL"],
    )

    # POSTGRES
    API_SERVER_POSTGRES: Optional[PostgresSettings]

    # SERVICES with http API
    API_SERVER_WEBSERVER: Optional[WebServerSettings]
    API_SERVER_CATALOG: Optional[CatalogSettings]
    API_SERVER_STORAGE: Optional[StorageSettings]
    API_SERVER_DIRECTOR_V2: Optional[DirectorV2Settings]
    API_SERVER_TRACING: Optional[TracingSettings]

    API_SERVER_DEV_FEATURES_ENABLED: bool = Field(
        False, env=["API_SERVER_DEV_FEATURES_ENABLED", "FAKE_API_SERVER_ENABLED"]
    )

    API_SERVER_REMOTE_DEBUG_PORT: int = 3000

    @cached_property
    def debug(self) -> bool:
        """If True, debug tracebacks should be returned on errors."""
        return self.SC_BOOT_MODE in [
            BootModeEnum.DEBUG,
            BootModeEnum.DEVELOPMENT,
            BootModeEnum.LOCAL,
        ]

    @validator("LOG_LEVEL", pre=True)
    @classmethod
    def _validate_loglevel(cls, value) -> str:
        return cls.validate_log_level(value)
