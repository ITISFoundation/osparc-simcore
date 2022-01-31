from pydantic import Field, HttpUrl, SecretStr
from settings_library.base import BaseCustomSettings

# TODO: read https://www.force11.org/group/resource-identification-initiative
SCICRUNCH_DEFAULT_URL = "https://scicrunch.org"


class SciCrunchSettings(BaseCustomSettings):

    SCICRUNCH_API_BASE_URL: HttpUrl = Field(
        f"{SCICRUNCH_DEFAULT_URL}/api/1",
        description="Base url to scicrunch API's entrypoint",
    )

    # NOTE: Login in https://scicrunch.org and get API Key under My Account -> API Keys
    # WARNING: this needs to be setup in osparc-ops before deploying
    SCICRUNCH_API_KEY: SecretStr

    SCICRUNCH_RESOLVER_BASE_URL: HttpUrl = Field(
        f"{SCICRUNCH_DEFAULT_URL}/resolver",
        description="Base url to scicrunch resolver entrypoint",
    )
