from pydantic import BaseSettings, Field, HttpUrl, SecretStr

# TODO: read https://www.force11.org/group/resource-identification-initiative
SCICRUNCH_DEFAULT_URL = "https://scicrunch.org"


class SciCrunchSettings(BaseSettings):

    api_base_url: HttpUrl = Field(
        f"{SCICRUNCH_DEFAULT_URL}/api/1",
        description="Base url to scicrunch API's entrypoint",
    )

    # NOTE: Login in https://scicrunch.org and get API Key under My Account -> API Keys
    # WARNING: this needs to be setup in osparc-ops before deploying
    api_key: SecretStr

    class Config:
        case_sensitive = False
        env_prefix = "SCICRUNCH_"
