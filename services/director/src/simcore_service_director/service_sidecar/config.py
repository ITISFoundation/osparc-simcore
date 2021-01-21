# this is a proxy for the global configuration and will be removed in the future
# making it easy to refactor

from pydantic import BaseSettings, Field
from aiohttp.web import Application

# this will be removed in the future
from .. import config as director_config


KEY_SERVICE_SIDECAR_SETTINGS = f"{__name__}.ServiceSidecarSettings"


class ServiceSidecarSettings(BaseSettings):
    # service_sidecar integration
    monitor_interval_seconds: int = Field(
        director_config.SERVICE_SIDECAR_MONITOR_INTERVAL_SECONDS, description="used "
    )


def setup_settings(app: Application) -> None:
    app[KEY_SERVICE_SIDECAR_SETTINGS] = ServiceSidecarSettings()


def get_settings(app: Application) -> ServiceSidecarSettings:
    return app[KEY_SERVICE_SIDECAR_SETTINGS]
