from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

from .services_types import ServiceKey, ServiceVersion
from .utils.common_validators import empty_str_to_none_pre_validator


class ServiceKeyVersion(BaseModel):
    """Service `key-version` pair uniquely identifies a service"""

    key: Annotated[
        ServiceKey,
        Field(
            ...,
            description="distinctive name for the node based on the docker registry path",
        ),
    ]
    version: Annotated[
        ServiceVersion,
        Field(
            description="service version number",
        ),
    ]

    model_config = ConfigDict(frozen=True)


class ServiceBaseDisplay(BaseModel):
    name: Annotated[
        str,
        Field(
            description="Display name: short, human readable name for the node",
            examples=["Fast Counter"],
        ),
    ]
    thumbnail: Annotated[
        str | None,
        Field(
            description="URL to the service thumbnail",
            validate_default=True,
        ),
    ] = None
    icon: Annotated[
        HttpUrl | None,
        Field(description="URL to the service icon"),
    ] = None
    description: Annotated[
        str,
        Field(
            description="human readable description of the purpose of the node",
            examples=[
                "Our best node type",
                "The mother of all nodes, makes your numbers shine!",
            ],
        ),
    ]
    description_ui: Annotated[
        bool,
        Field(
            description="A flag to enable the `description` to be presented as a single web page (=true) or in another structured format (default=false)."
        ),
    ] = False
    version_display: Annotated[
        str | None,
        Field(
            description="A user-friendly or marketing name for the release."
            "This can be used to reference the release in a more readable and recognizable format, such as 'Matterhorn Release,' 'Spring Update,' or 'Holiday Edition.' "
            "This name is not used for version comparison but is useful for communication and documentation purposes."
        ),
    ] = None

    _empty_is_none = field_validator(
        "icon", "thumbnail", "version_display", mode="before"
    )(empty_str_to_none_pre_validator)
