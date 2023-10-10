from functools import cached_property
from pathlib import Path

from models_library.basic_types import BootModeEnum, LogLevel
from pydantic import Field, SecretStr, parse_obj_as
from pydantic.class_validators import validator
from settings_library.base import BaseCustomSettings
from settings_library.basic_types import PortInt, VersionTag
from settings_library.catalog import CatalogSettings
from settings_library.postgres import PostgresSettings
from settings_library.storage import StorageSettings
from settings_library.utils_logging import MixinLoggingSettings
from settings_library.utils_service import (
    DEFAULT_AIOHTTP_PORT,
    DEFAULT_FASTAPI_PORT,
    MixinServiceSettings,
    URLPart,
)
from settings_library.utils_session import MixinSessionSettings


class WebServerSettings(BaseCustomSettings, MixinServiceSettings, MixinSessionSettings):
    WEBSERVER_HOST: str = "webserver"
    WEBSERVER_PORT: PortInt = DEFAULT_AIOHTTP_PORT
    WEBSERVER_VTAG: VersionTag = Field(default="v0")

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
        # http://webserver:8080/v0
        url_without_vtag: str = self._compose_url(
            prefix="WEBSERVER",
            port=URLPart.REQUIRED,
        )
        return url_without_vtag

    @cached_property
    def api_base_url(self) -> str:
        # http://webserver:8080/v0
        url_with_vtag: str = self._compose_url(
            prefix="WEBSERVER",
            port=URLPart.REQUIRED,
            vtag=URLPart.REQUIRED,
        )
        return url_with_vtag

    @validator("WEBSERVER_SESSION_SECRET_KEY")
    @classmethod
    def check_valid_fernet_key(cls, v):
        return cls.do_check_valid_fernet_key(v)


class DirectorV2Settings(BaseCustomSettings, MixinServiceSettings):
    DIRECTOR_V2_HOST: str = "director-v2"
    DIRECTOR_V2_PORT: PortInt = DEFAULT_FASTAPI_PORT
    DIRECTOR_V2_VTAG: VersionTag = parse_obj_as(VersionTag, "v2")

    @cached_property
    def api_base_url(self) -> str:
        # http://director-v2:8000/v2
        url_with_vtag: str = self._compose_url(
            prefix="DIRECTOR_V2",
            port=URLPart.REQUIRED,
            vtag=URLPart.REQUIRED,
        )
        return url_with_vtag

    @cached_property
    def base_url(self) -> str:
        # http://director-v2:8000
        origin: str = self._compose_url(
            prefix="DIRECTOR_V2",
            port=URLPart.REQUIRED,
            vtag=URLPart.EXCLUDE,
        )
        return origin


# MAIN SETTINGS --------------------------------------------


class BasicSettings(BaseCustomSettings, MixinLoggingSettings):
    # DEVELOPMENT
    API_SERVER_DEV_FEATURES_ENABLED: bool = Field(
        default=False,
        env=["API_SERVER_DEV_FEATURES_ENABLED", "FAKE_API_SERVER_ENABLED"],
    )

    # LOGGING
    LOG_LEVEL: LogLevel = Field(
        default=LogLevel.INFO.value,
        env=["API_SERVER_LOGLEVEL", "LOG_LEVEL", "LOGLEVEL"],
    )
    API_SERVER_LOG_FORMAT_LOCAL_DEV_ENABLED: bool = Field(
        default=False,
        env=["API_SERVER_LOG_FORMAT_LOCAL_DEV_ENABLED", "LOG_FORMAT_LOCAL_DEV_ENABLED"],
        description="Enables local development log format. WARNING: make sure it is disabled if you want to have structured logs!",
    )

    # DEBUGGING
    API_SERVER_REMOTE_DEBUG_PORT: int = 3000

    @validator("LOG_LEVEL", pre=True)
    @classmethod
    def _validate_loglevel(cls, value) -> str:
        log_level: str = cls.validate_log_level(value)
        return log_level


class ApplicationSettings(BasicSettings):
    # DOCKER BOOT
    SC_BOOT_MODE: BootModeEnum | None

    # POSTGRES
    API_SERVER_POSTGRES: PostgresSettings | None = Field(auto_default_from_env=True)

    # SERVICES with http API
    API_SERVER_WEBSERVER: WebServerSettings | None = Field(auto_default_from_env=True)
    API_SERVER_CATALOG: CatalogSettings | None = Field(auto_default_from_env=True)
    API_SERVER_STORAGE: StorageSettings | None = Field(auto_default_from_env=True)
    API_SERVER_DIRECTOR_V2: DirectorV2Settings | None = Field(
        auto_default_from_env=True
    )

    # DEV-TOOLS
    API_SERVER_DEV_HTTP_CALLS_LOGS_PATH: Path | None = Field(
        default=None,
        description="If set, it activates http calls capture mechanism used to generate mock data"
        "Path to store captured client calls."
        "TIP: use 'API_SERVER_DEV_HTTP_CALLS_LOGS_PATH=captures.ignore.keep.log'"
        "NOTE: only available in devel mode",
    )

    @cached_property
    def debug(self) -> bool:
        """If True, debug tracebacks should be returned on errors."""
        return self.SC_BOOT_MODE is not None and self.SC_BOOT_MODE.is_devel_mode()

    @validator("API_SERVER_DEV_HTTP_CALLS_LOGS_PATH")
    @classmethod
    def _enable_only_in_devel_mode(cls, v, values):
        if v and not (
            values
            and (boot_mode := values.get("SC_BOOT_MODE"))
            and boot_mode.is_devel_mode()
        ):
            msg = "API_SERVER_DEV_HTTP_CALLS_LOGS_PATH only allowed in devel mode"
            raise ValueError(msg)
        return v


__all__: tuple[str, ...] = (
    "ApplicationSettings",
    "BasicSettings",
    "CatalogSettings",
    "DirectorV2Settings",
    "StorageSettings",
    "WebServerSettings",
)
