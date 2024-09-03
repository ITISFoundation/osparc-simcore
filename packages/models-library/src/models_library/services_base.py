from pydantic import BaseModel, Field, HttpUrl, validator

from .services_types import ServiceKey, ServiceVersion
from .utils.common_validators import empty_str_to_none_pre_validator


class ServiceKeyVersion(BaseModel):
    """Service `key-version` pair uniquely identifies a service"""

    key: ServiceKey = Field(
        ...,
        description="distinctive name for the node based on the docker registry path",
    )
    version: ServiceVersion = Field(
        ...,
        description="service version number",
    )

    class Config:
        frozen = True


class ServiceBaseDisplay(BaseModel):
    name: str = Field(
        ...,
        description="Display name: short, human readable name for the node",
        example="Fast Counter",
    )
    thumbnail: HttpUrl | None = Field(
        None,
        description="url to the thumbnail",
        examples=[
            "https://user-images.githubusercontent.com/32800795/61083844-ff48fb00-a42c-11e9-8e63-fa2d709c8baf.png"
        ],
    )
    description: str = Field(
        ...,
        description="human readable description of the purpose of the node",
        examples=[
            "Our best node type",
            "The mother of all nodes, makes your numbers shine!",
        ],
    )
    description_ui: bool = Field(
        default=False,
        description="A flag to enable the `description` to be presented as a single web page (=true) or in another structured format (default=false).",
    )

    version_display: str | None = Field(
        None,
        description="A user-friendly or marketing name for the release."
        " This can be used to reference the release in a more readable and recognizable format, such as 'Matterhorn Release,' 'Spring Update,' or 'Holiday Edition.'"
        " This name is not used for version comparison but is useful for communication and documentation purposes.",
    )

    _empty_is_none = validator("thumbnail", allow_reuse=True, pre=True, always=False)(
        empty_str_to_none_pre_validator
    )
