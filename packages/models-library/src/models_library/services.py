import sys
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Union

from pydantic import BaseModel, EmailStr, Extra, Field, HttpUrl, constr, validator
from pydantic.types import PositiveInt

from .constants import VERSION_RE

current_file = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve()


KEY_RE = r"^(simcore)/(services)/(comp|dynamic|frontend)(/[^\s/]+)+$"
PROPERTY_TYPE_RE = r"^(number|integer|boolean|string|data:([^/\s,]+/[^/\s,]+|\[[^/\s,]+/[^/\s,]+(,[^/\s]+/[^/,\s]+)*\]))$"

PROPERTY_KEY_RE = r"^[-_a-zA-Z0-9]+$"
FILENAME_RE = r".+"

PropertyName = constr(regex=PROPERTY_KEY_RE)
FileName = constr(regex=FILENAME_RE)
GroupId = PositiveInt


# Service base schema (used for docker labels on docker images)


class ServiceType(str, Enum):
    frontend = "frontend"
    computational = "computational"
    dynamic = "dynamic"


class Badge(BaseModel):
    name: str = Field(
        ...,
        description="Name of the subject",
        example=["travis-ci", "coverals.io", "github.io"],
    )
    image: HttpUrl = Field(
        ...,
        description="Url to the badge",
        example=[
            "https://travis-ci.org/ITISFoundation/osparc-simcore.svg?branch=master",
            "https://coveralls.io/repos/github/ITISFoundation/osparc-simcore/badge.svg?branch=master",
            "https://img.shields.io/website-up-down-green-red/https/itisfoundation.github.io.svg?label=documentation",
        ],
    )
    url: HttpUrl = Field(
        ...,
        description="Link to the status",
        example=[
            "https://travis-ci.org/ITISFoundation/osparc-simcore 'State of CI: build, test and pushing images'",
            "https://coveralls.io/github/ITISFoundation/osparc-simcore?branch=master 'Test coverage'",
            "https://itisfoundation.github.io/",
        ],
    )

    class Config:
        extra = Extra.forbid


class Author(BaseModel):
    name: str = Field(..., description="Name of the author", example="Jim Knopf")
    email: EmailStr = Field(
        ...,
        example=["sun@sense.eight", "deleen@minbar.bab"],
        description="Email address",
    )
    affiliation: Optional[str] = Field(
        None, example=["Sense8", "Babylon 5"], description="Affiliation of the author"
    )

    class Config:
        extra = Extra.forbid


class WidgetType(str, Enum):
    TextArea = "TextArea"
    SelectBox = "SelectBox"


class TextArea(BaseModel):
    min_height: PositiveInt = Field(
        ..., alias="minHeight", description="minimum Height of the textarea"
    )

    class Config:
        extra = Extra.forbid


class Structure(BaseModel):
    key: Union[str, bool, float]
    label: str

    class Config:
        extra = Extra.forbid


class SelectBox(BaseModel):
    structure: List[Structure] = Field(..., min_items=1)

    class Config:
        extra = Extra.forbid


class Widget(BaseModel):
    widget_type: WidgetType = Field(
        ..., alias="type", description="type of the property"
    )
    details: Union[TextArea, SelectBox]

    class Config:
        extra = Extra.forbid


class ServiceProperty(BaseModel):
    display_order: float = Field(
        ...,
        alias="displayOrder",
        description="use this to numerically sort the properties for display",
        example=[1, -0.2],
    )
    label: str = Field(..., description="short name for the property", example="Age")
    description: str = Field(
        ...,
        description="description of the property",
        example="Age in seconds since 1970",
    )
    property_type: constr(regex=PROPERTY_TYPE_RE) = Field(
        ...,
        alias="type",
        description="data type expected on this input glob matching for data type is allowed",
        example=[
            "number",
            "boolean",
            "data:*/*",
            "data:text/*",
            "data:[image/jpeg,image/png]",
            "data:application/json",
            "data:application/json;schema=https://my-schema/not/really/schema.json",
            "data:application/vnd.ms-excel",
            "data:text/plain",
            "data:application/hdf5",
            "data:application/edu.ucdavis@ceclancy.xyz",
        ],
    )
    file_to_key_map: Optional[Dict[FileName, PropertyName]] = Field(
        None,
        alias="fileToKeyMap",
        description="Place the data associated with the named keys in files",
        example=[{"dir/input1.txt": "key_1", "dir33/input2.txt": "key2"}],
    )
    default_value: Optional[Union[str, float, bool, int]] = Field(
        None, alias="defaultValue", example=["Dog", True]
    )

    class Config:
        extra = Extra.forbid


class ServiceInput(ServiceProperty):
    widget: Optional[Widget] = Field(
        None,
        description="custom widget to use instead of the default one determined from the data-type",
    )


class ServiceOutput(ServiceProperty):
    pass


class ServiceKeyVersion(BaseModel):
    key: constr(regex=KEY_RE) = Field(
        ...,
        title="",
        description="distinctive name for the node based on the docker registry path",
        example=[
            "simcore/services/comp/itis/sleeper",
            "simcore/services/dynamic/3dviewer",
        ],
    )
    version: constr(regex=VERSION_RE) = Field(
        ...,
        description="service version number",
        example=["1.0.0", "0.0.1"],
    )


class ServiceCommonData(BaseModel):
    name: str = Field(
        ...,
        description="short, human readable name for the node",
        example="Fast Counter",
    )
    thumbnail: Optional[HttpUrl] = Field(
        None,
        description="url to the thumbnail",
        example="https://user-images.githubusercontent.com/32800795/61083844-ff48fb00-a42c-11e9-8e63-fa2d709c8baf.png",
    )
    description: str = Field(
        ...,
        description="human readable description of the purpose of the node",
        example=[
            "Our best node type",
            "The mother of all nodes, makes your numbers shine!",
        ],
    )

    @validator("thumbnail", pre=True, always=False)
    def validate_thumbnail(cls, value):  # pylint: disable=no-self-argument,no-self-use
        if value == "":
            return None
        return value


ServiceInputs = Dict[PropertyName, ServiceInput]
ServiceOutputs = Dict[PropertyName, ServiceOutput]


class ServiceDockerData(ServiceKeyVersion, ServiceCommonData):
    integration_version: Optional[constr(regex=VERSION_RE)] = Field(
        None,
        alias="integration-version",
        description="integration version number",
        # regex=VERSION_RE,
        example="1.0.0",
    )
    service_type: ServiceType = Field(
        ...,
        alias="type",
        description="service type",
        example="computational",
    )

    badges: Optional[List[Badge]] = Field(None)

    authors: List[Author] = Field(..., min_items=1)
    contact: EmailStr = Field(
        ...,
        description="email to correspond to the authors about the node",
        example=["lab@net.flix"],
    )
    inputs: Optional[ServiceInputs] = Field(
        ..., description="definition of the inputs of this node"
    )
    outputs: Optional[ServiceOutputs] = Field(
        ..., description="definition of the outputs of this node"
    )

    class Config:
        description = "Description of a simcore node 'class' with input and output"
        title = "simcore node"
        extra = Extra.forbid


# Service access rights models


class ServiceGroupAccessRights(BaseModel):
    execute_access: bool = Field(
        False,
        description="defines whether the group can execute the service",
    )
    write_access: bool = Field(
        False, description="defines whether the group can modify the service"
    )


class ServiceAccessRights(BaseModel):
    access_rights: Optional[Dict[GroupId, ServiceGroupAccessRights]] = Field(
        None, description="service access rights per group id"
    )


class ServiceMetaData(ServiceCommonData):
    # for a partial update all members must be Optional
    name: Optional[str]
    thumbnail: Optional[HttpUrl]
    description: Optional[str]
    classifiers: Optional[List[str]]


# Databases models (tables services_meta_data and services_access_rights)
class ServiceMetaDataAtDB(ServiceKeyVersion, ServiceMetaData):
    # for a partial update all members must be Optional
    classifiers: Optional[List[str]] = Field([])
    owner: Optional[PositiveInt]

    class Config:
        orm_mode = True


class ServiceAccessRightsAtDB(ServiceKeyVersion, ServiceGroupAccessRights):
    gid: PositiveInt = Field(..., description="defines the group id", example=1)
    product_name: str = Field(
        ..., description="defines the product name", example="osparc"
    )

    class Config:
        orm_mode = True


if __name__ == "__main__":

    with open(current_file.with_suffix(".json"), "wt") as fh:
        print(ServiceDockerData.schema_json(indent=2), file=fh)
