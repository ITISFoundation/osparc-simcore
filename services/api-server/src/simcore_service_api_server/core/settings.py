from functools import cached_property
from typing import Optional

from models_library.basic_types import BootModeEnum, LogLevel
from pydantic import AnyHttpUrl, Field, SecretStr
from pydantic.class_validators import validator
from servicelib.statics_constants import FRONTEND_APP_DEFAULT
from settings_library.base import BaseCustomSettings
from settings_library.catalog import CatalogSettings
from settings_library.postgres import PostgresSettings
from settings_library.tracing import TracingSettings
from settings_library.utils_logging import MixinLoggingSettings
from settings_library.utils_session import MixinSessionSettings

# SERVICES CLIENTS --------------------------------------------


class _UrlMixin:
    def _build_url(self, prefix: str) -> str:
        prefix = prefix.upper()
        return AnyHttpUrl.build(
            scheme="http",
            host=getattr(self, f"{prefix}_HOST"),
            port=f"{getattr(self, f'{prefix}_PORT')}",
            path=f"/{getattr(self, f'{prefix}_VTAG')}",  # NOTE: it ends with /{VTAG}
        )


class WebServerSettings(BaseCustomSettings, _UrlMixin, MixinSessionSettings):
    WEBSERVER_HOST: str = "webserver"
    WEBSERVER_PORT: int = 8080
    WEBSERVER_VTAG: str = "v0"

    WEBSERVER_SESSION_SECRET_KEY: SecretStr = Field(
        ...,
        description="Secret key to encrypt cookies. "
        'TIP: python3 -c "from cryptography.fernet import *; print(Fernet.generate_key())"',
        min_length=44,
        env=["SESSION_SECRET_KEY", "WEBSERVER_SESSION_SECRET_KEY"],
    )
    WEBSERVER_SESSION_NAME: str = "osparc.WEBAPI_SESSION"

    @cached_property
    def base_url(self) -> str:
        return self._build_url("WEBSERVER")

    @validator("WEBSERVER_SESSION_SECRET_KEY")
    @classmethod
    def check_valid_fernet_key(cls, v):
        return cls.do_check_valid_fernet_key(v)


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
        return self._build_url("DIRECTOR_V2")


# MAIN SETTINGS --------------------------------------------


class BasicSettings(BaseCustomSettings, MixinLoggingSettings):

    # DEVELOPMENT
    API_SERVER_DEV_FEATURES_ENABLED: bool = Field(
        False, env=["API_SERVER_DEV_FEATURES_ENABLED", "FAKE_API_SERVER_ENABLED"]
    )

    # LOGGING
    LOG_LEVEL: LogLevel = Field(
        LogLevel.INFO.value,
        env=["API_SERVER_LOGLEVEL", "LOG_LEVEL", "LOGLEVEL"],
    )

    # DEBUGGING
    API_SERVER_REMOTE_DEBUG_PORT: int = 3000

    @validator("LOG_LEVEL", pre=True)
    @classmethod
    def _validate_loglevel(cls, value) -> str:
        return cls.validate_log_level(value)


class ApplicationSettings(BasicSettings):

    # DOCKER BOOT
    SC_BOOT_MODE: Optional[BootModeEnum]

    # POSTGRES
    API_SERVER_POSTGRES: Optional[PostgresSettings] = Field(auto_default_from_env=True)

    # SERVICES with http API
    API_SERVER_WEBSERVER: Optional[WebServerSettings] = Field(
        auto_default_from_env=True
    )
    API_SERVER_CATALOG: Optional[CatalogSettings] = Field(auto_default_from_env=True)
    API_SERVER_STORAGE: Optional[StorageSettings] = Field(auto_default_from_env=True)
    API_SERVER_DIRECTOR_V2: Optional[DirectorV2Settings] = Field(
        auto_default_from_env=True
    )
    API_SERVER_DEFAULT_PRODUCT_NAME: str = Field(
        default=FRONTEND_APP_DEFAULT, description="The API-server default product name"
    )

    # DIAGNOSTICS
    API_SERVER_TRACING: Optional[TracingSettings] = Field(auto_default_from_env=True)

    @cached_property
    def debug(self) -> bool:
        """If True, debug tracebacks should be returned on errors."""
        return self.SC_BOOT_MODE in [
            BootModeEnum.DEBUG,
            BootModeEnum.DEVELOPMENT,
            BootModeEnum.LOCAL,
        ]
