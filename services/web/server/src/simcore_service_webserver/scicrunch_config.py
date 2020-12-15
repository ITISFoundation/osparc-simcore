from pydantic import BaseSettings, Field, HttpUrl, SecretStr

# TODO: read https://www.force11.org/group/resource-identification-initiative
SCICRUNCH_DEFAULT_URL = "https://scicrunch.org"

# To ensure they are recognizable, unique, and traceable, identifiers are prefixed with " RRID: ",
# followed by a second tag that indicates the source authority that provided it
# (e.g. "AB" for the Antibody Registry, "CVCL" for the Cellosaurus, "MMRRC" for Mutant Mouse Regional Resource Centers,
# "SCR" for the SciCrunch registry of tools).
# SEE https://scicrunch.org/resources

RRID_PATTERN = r"(RRID:)?\s*(SCR_\d+)"


class SciCrunchSettings(BaseSettings):

    api_base_url: HttpUrl = Field(
        f"{SCICRUNCH_DEFAULT_URL}/api/1",
        description="Base url to scicrunch API's entrypoint",
    )

    # Login in https://scicrunch.org and get API Key under My Account -> API Keys
    api_key: SecretStr

    new_submission_url: HttpUrl = Field(
        f"{SCICRUNCH_DEFAULT_URL}/resources/about/resource",
        description="Url with the submission form for a new resource",
    )

    class Config:
        env_prefix = "KCORE_SCICRUNCH_"
