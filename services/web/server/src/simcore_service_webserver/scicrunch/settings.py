from typing import Annotated

from aiohttp import web
from pydantic import Field, HttpUrl, SecretStr, TypeAdapter
from settings_library.base import BaseCustomSettings

from ..application_keys import APP_SETTINGS_APPKEY

# TODO: read https://www.force11.org/group/resource-identification-initiative
SCICRUNCH_DEFAULT_URL = "https://scicrunch.org"


class SciCrunchSettings(BaseCustomSettings):
    SCICRUNCH_API_BASE_URL: Annotated[
        HttpUrl, Field(description="Base url to scicrunch API's entrypoint")
    ] = TypeAdapter(HttpUrl).validate_python(f"{SCICRUNCH_DEFAULT_URL}/api/1")

    # NOTE: Login in https://scicrunch.org and get API Key under My Account -> API Keys
    # WARNING: this needs to be setup in osparc-ops before deploying
    SCICRUNCH_API_KEY: SecretStr

    SCICRUNCH_RESOLVER_BASE_URL: Annotated[
        HttpUrl, Field(description="Base url to scicrunch resolver entrypoint")
    ] = TypeAdapter(HttpUrl).validate_python(f"{SCICRUNCH_DEFAULT_URL}/resolver")


def get_plugin_settings(app: web.Application) -> SciCrunchSettings:
    settings = app[APP_SETTINGS_APPKEY].WEBSERVER_SCICRUNCH
    assert settings, "setup_settings not called?"  # nosec
    assert isinstance(settings, SciCrunchSettings)  # nosec
    return settings
