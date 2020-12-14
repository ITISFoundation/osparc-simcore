from pydantic import BaseSettings, Field, HttpUrl, SecretStr


class SciCrunchSettings(BaseSettings):
    api_base_url: HttpUrl = Field(
        "https://scicrunch.org/api/1",
        description="Base url to scicrunch API entrypoint",
    )
    api_key: SecretStr
    # Login in https://scicrunch.org and get API Key under My Account -> API Keys

    class Config:
        env_prefix = "KCORE_SCICRUNCH_"
