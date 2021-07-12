"""
     Bases to build ApplicationSettings

     TODO: when py 3.7 the use https://pydantic-docs.helpmanual.io/usage/models/#generic-models
"""
import logging
from typing import Optional

from pydantic import AnyHttpUrl, BaseSettings, Field, validator

from ..basic_types import BootModeEnum, LogLevel, PortInt, VersionTag


class BaseFastApiAppSettings(BaseSettings):
    # DOCKER
    boot_mode: Optional[BootModeEnum] = Field(..., env="SC_BOOT_MODE")

    # LOGGING
    log_level: LogLevel = Field("DEBUG", env=["LOG_LEVEL", "LOGLEVEL"])

    @property
    def logging_level(self) -> int:
        return getattr(logging, self.log_level)

    # SERVER (see : https://www.uvicorn.org/settings/)
    host: str = "0.0.0.0"  # nosec
    port: PortInt = 8000
    debug: bool = False  # If True, debug tracebacks should be returned on errors.

    # DEBUGGING
    remote_debug_port: PortInt = 3000


class BaseAiohttpAppSettings(BaseFastApiAppSettings):
    port: PortInt = 8080


class BaseServiceAPISettings(BaseSettings):
    host: str
    port: PortInt
    vtag: VersionTag = Field("v0", description="Service API's version tag")

    url: Optional[AnyHttpUrl] = None

    @validator("url", pre=True)
    @classmethod
    def autofill_url(cls, v, values):
        if v is None:
            return AnyHttpUrl.build(
                scheme="http",
                host=values["host"],
                port=f"{values['port']}",
                path=f"/{values['vtag']}",
            )
        return v
