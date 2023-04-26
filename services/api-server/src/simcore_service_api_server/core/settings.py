from functools import cached_property
from pathlib import Path

from models_library.basic_types import BootModeEnum, LogLevel
from pydantic import AnyHttpUrl, Field, SecretStr
from pydantic.class_validators import validator
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
        url: str = AnyHttpUrl.build(
            scheme="http",
            host=getattr(self, f"{prefix}_HOST"),
            port=f"{getattr(self, f'{prefix}_PORT')}",
            path=f"/{getattr(self, f'{prefix}_VTAG')}",  # NOTE: it ends with /{VTAG}
        )
        return url


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

    # DIAGNOSTICS
    API_SERVER_TRACING: TracingSettings | None = Field(auto_default_from_env=True)

    # DEV-TOOLS
    API_SERVER_HTTP_CALLS_CAPTURE_LOGS_PATH: Path | None = Field(
        default=None,
        description="If set, it activates http calls capture mechanism used to generate mock data"
        "Path to store captured client calls."
        "TIP: use 'API_SERVER_HTTP_CALLS_CAPTURE_LOGS_PATH=captures.ignore.keep.log'"
        "NOTE: only available in devel mode",
    )

    @cached_property
    def debug(self) -> bool:
        """If True, debug tracebacks should be returned on errors."""
        return self.SC_BOOT_MODE is not None and self.SC_BOOT_MODE.is_devel_mode()

    @validator("API_SERVER_HTTP_CALLS_CAPTURE_LOGS_PATH")
    @classmethod
    def _only_in_devel_mode(cls, v, values):
        if (
            values
            and (boot_mode := values.get("SC_BOOT_MODE"))
            and boot_mode.is_devel_mode()
        ):
            return v
        raise ValueError("API_SERVER_CAPTURE_PATH only allowed in devel mode")
