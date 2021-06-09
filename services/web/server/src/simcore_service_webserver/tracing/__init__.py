import logging
from typing import Optional

from aiohttp import web
from models_library.settings.base import BaseCustomSettings
from pydantic import AnyHttpUrl
from servicelib.application_setup import ModuleCategory, app_module_setup
from servicelib.tracing import setup_tracing

from .constants import APP_CONFIG_KEY
from .settings import Settings

CONFIG_SECTION_NAME = "tracing"

log = logging.getLogger(__name__)


class TracingSettings(BaseCustomSettings):
    TRACING_ENABLED: Optional[bool] = True
    TRACING_ZIPKIN_ENDPOINT: AnyHttpUrl = "http://jaeger:9411"


@app_module_setup(__name__, ModuleCategory.ADDON, logger=log)
def setup(app: web.Application):
    config: Settings = app[APP_CONFIG_KEY]
    host = config["main"]["host"]
    port = config["main"]["port"]
    return setup_tracing(
        app, "simcore_service_webserver", host, port, config["tracing"]
    )


# alias
setup_app_tracing = setup
tracing_section_name = CONFIG_SECTION_NAME
__all__ = ("setup_app_tracing", "tracing_section_name")
