"""
TODO: pydantic settings comming soon and replacing trafaret

"""
import logging
from typing import Dict, Optional

from aiohttp import web
from pydantic import BaseSettings, Field

from ._meta import api_version, app_name
from .constants import APP_SETTINGS_KEY
from .utils import snake_to_camel


log = logging.getLogger(__name__)



class ApplicationSettings(BaseSettings):
    # CODE STATICS ---
    # settings defined by the code

    app_name: str = app_name
    api_version: str = api_version

    # IMAGE BUILD ---
    # settings defined when docker image is built
    #

    vcs_url: Optional[str] = Field(None, env="SC_VCS_URL")
    vcs_ref: Optional[str] = Field(None, env="SC_VCS_REF")
    build_date: Optional[str] = Field(None, env="SC_BUILD_DATE")
    build_target: Optional[str] = Field(None, env="SC_BUILD_TARGET")

    boot_mode: Optional[str] = Field(None, env="SC_BOOT_MODE")
    user_name: Optional[str] = Field(None, env="SC_USER_NAME")
    user_id: Optional[int] = Field(None, env="SC_USER_ID")

    heathcheck_retry: Optional[int] = Field(None, env="SC_HEATHCHECK_RETRY")
    heatcheck_inteval: Optional[int] = Field(None, env="SC_HEATCHECK_INTEVAL")

    # stack name defined upon deploy (see main Makefile)
    swarm_stack_name: Optional[str] = Field(
        None, alias="stackName", env="SWARM_STACK_NAME"
    )

    # CONTAINER RUN  ---
    # settings defined from environs defined when container runs


    class Config:
        env_prefix = "WEBSERVER_"
        case_sensitive = False
        alias_generator = snake_to_camel

    # ---

    def public_dict(self) -> Dict:
        """ Data publicaly available  """
        return self.dict(
            include={"app_name", "api_version", "vcs_url", "vcs_ref", "build_date"},
            exclude_none=True,
        )

    def to_client_statics(self) -> Dict:
        return self.dict(
            include={
                "app_name",
                "api_version",
                "vcs_url",
                "vcs_ref",
                "build_date",
                "swarm_stack_name",
            },
            exclude_none=True,
            by_alias=True,
        )


def setup_settings(app: web.Application):
    app[APP_SETTINGS_KEY] = ApplicationSettings()
    log.info("Captured app settings:\n%s", app[APP_SETTINGS_KEY].json(indent=2))
