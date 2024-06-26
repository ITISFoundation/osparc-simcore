from pydantic import BaseModel, Field, HttpUrl, validator

from .services_types import ServiceKey, ServiceVersion
from .utils.common_validators import empty_str_to_none_pre_validator


class ServiceKeyVersion(BaseModel):
    """This pair uniquely identifies a services"""

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


class ServiceBase(BaseModel):
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

    _empty_is_none = validator("thumbnail", allow_reuse=True, pre=True, always=False)(
        empty_str_to_none_pre_validator
    )
