from aiohttp import web
from pydantic import Field, HttpUrl, SecretStr, TypeAdapter
from settings_library.base import BaseCustomSettings

from .._constants import APP_SETTINGS_KEY

# TODO: read https://www.force11.org/group/resource-identification-initiative
SCICRUNCH_DEFAULT_URL = "https://scicrunch.org"


class SciCrunchSettings(BaseCustomSettings):

    SCICRUNCH_API_BASE_URL: HttpUrl = Field(
        default=TypeAdapter(HttpUrl).validate_python(f"{SCICRUNCH_DEFAULT_URL}/api/1"),
        description="Base url to scicrunch API's entrypoint",
    )

    # NOTE: Login in https://scicrunch.org and get API Key under My Account -> API Keys
    # WARNING: this needs to be setup in osparc-ops before deploying
    SCICRUNCH_API_KEY: SecretStr

    SCICRUNCH_RESOLVER_BASE_URL: HttpUrl = Field(
        default=TypeAdapter(HttpUrl).validate_python(
            f"{SCICRUNCH_DEFAULT_URL}/resolver"
        ),
        description="Base url to scicrunch resolver entrypoint",
    )


def get_plugin_settings(app: web.Application) -> SciCrunchSettings:
    settings = app[APP_SETTINGS_KEY].WEBSERVER_SCICRUNCH
    assert settings, "setup_settings not called?"  # nosec
    assert isinstance(settings, SciCrunchSettings)  # nosec
    return settings
