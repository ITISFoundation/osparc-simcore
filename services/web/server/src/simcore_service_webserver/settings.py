"""
TODO: pydantic settings comming soon and replacing trafaret

"""
import logging
from typing import Dict, Optional

from aiohttp import web
from pydantic import BaseSettings

APP_SETTINGS_KEY = f"{__name__ }.build_time_settings"

log = logging.getLogger(__name__)


class BuildTimeSettings(BaseSettings):
    # All these settings are defined in the Dockerfile at build-image time
    vsc_url: Optional[str] = None
    vsc_ref: Optional[str] = None
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
            include={"vsc_url", "vsc_ref", "build_date"},
            exclude_unset=True,
            exclude_none=True,
        )


def setup_settings(app: web.Application):
    app[APP_SETTINGS_KEY] = BuildTimeSettings()
    log.info("Captured app settings:\n%s", app[APP_SETTINGS_KEY].json(indent=2))
