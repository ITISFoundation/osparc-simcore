"""
TODO: pydantic settings comming soon and replacing trafaret

"""
import logging
from typing import Dict, Optional

from aiohttp import web
from pydantic import BaseSettings

from .__version__ import app_name, api_version

APP_SETTINGS_KEY = f"{__name__ }.app_settings"

log = logging.getLogger(__name__)


class ApplicationSettings(BaseSettings):
    # settings defined by the code
    app_name: str = app_name
    api_version: str = api_version

    # settings defined when docker image is built
    vcs_url: Optional[str] = None
    vcs_ref: Optional[str] = None
    build_date: Optional[str] = None
    build_target: Optional[str] = None

    boot_mode: Optional[str] = None
    user_name: Optional[str] = None
    user_id: Optional[int] = None

    heathcheck_retry: Optional[int] = None
    heatcheck_inteval: Optional[int] = None

    class Config:
        env_prefix = "SC_"
        case_sensitive = False

    # ---

    def public_dict(self) -> Dict:
        """ Data publicaly available  """
        return self.dict(
            include={"vcs_url", "vcs_ref", "build_date", "app_name", "api_version"},
            exclude_none=True,
        )


def setup_settings(app: web.Application):
    app[APP_SETTINGS_KEY] = ApplicationSettings()
    log.info("Captured app settings:\n%s", app[APP_SETTINGS_KEY].json(indent=2))
