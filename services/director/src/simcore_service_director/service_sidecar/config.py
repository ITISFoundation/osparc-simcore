# this is a proxy for the global configuration and will be removed in the future
# making it easy to refactor

from pydantic import BaseSettings, Field
from aiohttp.web import Application


KEY_SERVICE_SIDECAR_SETTINGS = f"{__name__}.ServiceSidecarSettings"


class ServiceSidecarSettings(BaseSettings):
    # service_sidecar integration
    monitor_interval_seconds: float = Field(
        5.0, description="interval at which the monitor cycle is repeated"
    )

    class Config:
        case_sensitive = False
        env_prefix = "SERVICE_SIDECAR_"


def setup_settings(app: Application) -> None:
    app[KEY_SERVICE_SIDECAR_SETTINGS] = ServiceSidecarSettings()


def get_settings(app: Application) -> ServiceSidecarSettings:
    return app[KEY_SERVICE_SIDECAR_SETTINGS]
