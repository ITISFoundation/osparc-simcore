import logging
from typing import Any, Dict, Optional

from aiohttp import web
from models_library.basic_types import BootModeEnum, BuildTargetEnum
from pydantic import Field
from pydantic.types import SecretStr
from settings_library.base import BaseCustomSettings

from ._constants import APP_SETTINGS_KEY
from ._meta import API_VERSION, APP_NAME
from .catalog_settings import CatalogSettings
from .db_settings import PostgresSettings
from .storage_settings import StorageSettings
from .utils import snake_to_camel

log = logging.getLogger(__name__)


class ApplicationSettings(BaseCustomSettings):
    # CODE STATICS ---
    API_VERSION: str = API_VERSION
    APP_NAME: str = APP_NAME

    # IMAGE BUILDTIME ---
    SC_BUILD_DATE: Optional[str] = None
    SC_BUILD_TARGET: Optional[BuildTargetEnum] = None
    SC_VCS_REF: Optional[str] = None
    SC_VCS_URL: Optional[str] = None

    # @Dockerfile
    SC_BOOT_MODE: Optional[BootModeEnum]
    SC_HEATCHECK_INTEVAL: Optional[int] = None
    SC_HEATHCHECK_RETRY: Optional[int] = None
    SC_USER_ID: Optional[int] = None
    SC_USER_NAME: Optional[str] = None

    # RUNTIME  ---
    # settings defined from environs defined when container runs
    # NOTE: keep alphabetically if possible

    SWARM_STACK_NAME: Optional[str] = Field(
        None, description="stack name defined upon deploy (see main Makefile)"
    )

    WEBSERVER_DEV_FEATURES_ENABLED: bool = Field(
        False,
        description="Enables development features. WARNING: make sure it is disabled in production .env file!",
    )

    # POSTGRES
    WEBSERVER_POSTGRES: Optional[PostgresSettings]

    # SESSION
    WEBSERVER_SESSION_SECRET_KEY: SecretStr(min_length=32) = Field(  # type: ignore
        ..., description="Secret key to encrypt cookies"
    )

    # SERVICES with http API
    WEBSERVER_CATALOG: Optional[CatalogSettings]
    WEBSERVER_STORAGE: Optional[StorageSettings]
    # WEBSERVER_DIRECTOR_V2: Optional[DirectorV2Settings]
    # WEBSERVER_TRACING: Optional[TracingSettings]

    class Config(BaseCustomSettings.Config):
        fields = {
            "SC_VCS_URL": "vcs_url",
            "SC_VCS_REF": "vcs_ref",
            "SC_BUILD_DATE": "build_date",
            "SWARM_STACK_NAME": "stack_name",
        }
        alias_generator = lambda s: s.lower()

    def public_dict(self) -> Dict[str, Any]:
        """Data publicaly available"""
        return self.dict(
            include={
                "APP_NAME",
                "API_VERSION",
                "SC_VCS_URL",
                "SC_VCS_REF",
                "SC_BUILD_DATE",
            },
            exclude_none=True,
            by_alias=True,
        )

    def to_client_statics(self) -> Dict[str, Any]:
        data = self.dict(
            include={
                "APP_NAME",
                "API_VERSION",
                "SC_VCS_URL",
                "SC_VCS_REF",
                "SC_BUILD_DATE",
                "SWARM_STACK_NAME",
            },
            exclude_none=True,
            by_alias=True,
        )
        # Alias MUST be camelcase here
        return {snake_to_camel(k): v for k, v in data.items()}


def setup_settings(app: web.Application):
    app[APP_SETTINGS_KEY] = ApplicationSettings()
    log.info("Captured app settings:\n%s", app[APP_SETTINGS_KEY].json(indent=2))
