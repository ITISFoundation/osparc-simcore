from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from .emails import LowerCaseEmailStr


class Badge(BaseModel):
    name: str = Field(
        ...,
        description="Name of the subject",
    )
    image: HttpUrl = Field(
        ...,
        description="Url to the badge",
    )
    url: HttpUrl = Field(
        ...,
        description="Link to the status",
    )
    model_config = ConfigDict()


class Author(BaseModel):
    name: str = Field(
        ...,
        description="Name of the author",
    )
    email: LowerCaseEmailStr = Field(
        ...,
        description="Email address",
    )
    affiliation: str | None = Field(None)
    model_config = ConfigDict()
