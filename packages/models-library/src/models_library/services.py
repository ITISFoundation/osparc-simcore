"""

NOTE: to dump json-schema from CLI use
    python -c "from models_library.services import ServiceDockerData as cls; print(cls.schema_json(indent=2))" > services-schema.json
"""
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import (
    BaseModel,
    EmailStr,
    Extra,
    Field,
    HttpUrl,
    StrictBool,
    StrictFloat,
    StrictInt,
    constr,
    validator,
)
from pydantic.types import PositiveInt

from .basic_regex import VERSION_RE

# NOTE: needs to end with / !!
SERVICE_KEY_RE = r"^(simcore)/(services)/(comp|dynamic|frontend)(/[\w/-]+)+$"

DYNAMIC_SERVICE_KEY_RE = r"^(simcore)/(services)/dynamic(/[\w/-]+)+$"
DYNAMIC_SERVICE_KEY_FORMAT = "simcore/services/dynamic/{service_name}"

COMPUTATIONAL_SERVICE_KEY_RE = r"^(simcore)/(services)/comp(/[\w/-]+)+$"
COMPUTATIONAL_SERVICE_KEY_FORMAT = "simcore/services/comp/{service_name}"

KEY_RE = SERVICE_KEY_RE  # TODO: deprecate this global constant by SERVICE_KEY_RE

SERVICE_NETWORK_RE = r"^([a-zA-Z0-9_-]+)$"


PROPERTY_TYPE_RE = r"^(number|integer|boolean|string|data:([^/\s,]+/[^/\s,]+|\[[^/\s,]+/[^/\s,]+(,[^/\s]+/[^/,\s]+)*\]))$"
PROPERTY_KEY_RE = r"^[-_a-zA-Z0-9]+$"

FILENAME_RE = r".+"

PropertyName = constr(regex=PROPERTY_KEY_RE)
FileName = constr(regex=FILENAME_RE)
GroupId = PositiveInt


class ServiceType(str, Enum):
    COMPUTATIONAL = "computational"
    DYNAMIC = "dynamic"
    FRONTEND = "frontend"


class Badge(BaseModel):
    name: str = Field(
        ...,
        description="Name of the subject",
        examples=["travis-ci", "coverals.io", "github.io"],
    )
    image: HttpUrl = Field(
        ...,
        description="Url to the badge",
        examples=[
            "https://travis-ci.org/ITISFoundation/osparc-simcore.svg?branch=master",
            "https://coveralls.io/repos/github/ITISFoundation/osparc-simcore/badge.svg?branch=master",
            "https://img.shields.io/website-up-down-green-red/https/itisfoundation.github.io.svg?label=documentation",
        ],
    )
    url: HttpUrl = Field(
        ...,
        description="Link to the status",
        examples=[
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
        examples=["sun@sense.eight", "deleen@minbar.bab"],
        description="Email address",
    )
    affiliation: Optional[str] = Field(
        None, examples=["Sense8", "Babylon 5"], description="Affiliation of the author"
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
    """
    Metadata on a service input or output port
    """

    ## management

    ### human readable descriptors
    display_order: Optional[float] = Field(
        None,
        alias="displayOrder",
        deprecated=True,
        description="DEPRECATED: new display order is taken from the item position. This will be removed.",
    )

    label: str = Field(..., description="short name for the property", example="Age")
    description: str = Field(
        ...,
        description="description of the property",
        example="Age in seconds since 1970",
    )

    # mathematical and physics descriptors
    property_type: str = Field(
        ...,
        alias="type",
        description="data type expected on this input glob matching for data type is allowed",
        examples=[
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
        regex=PROPERTY_TYPE_RE,
    )

    # value
    file_to_key_map: Optional[Dict[FileName, PropertyName]] = Field(
        None,
        alias="fileToKeyMap",
        description="Place the data associated with the named keys in files",
        examples=[{"dir/input1.txt": "key_1", "dir33/input2.txt": "key2"}],
    )

    # TODO: use discriminators
    unit: Optional[str] = Field(
        None, description="Units, when it refers to a physical quantity"
    )

    class Config:
        extra = Extra.forbid
        # TODO: all alias with camecase


class ServiceInput(ServiceProperty):
    """
    Metadata on a service input port
    """

    default_value: Optional[Union[StrictBool, StrictInt, StrictFloat, str]] = Field(
        None, alias="defaultValue", examples=["Dog", True]
    )

    widget: Optional[Widget] = Field(
        None,
        description="custom widget to use instead of the default one determined from the data-type",
    )

    class Config(ServiceProperty.Config):
        schema_extra = {
            "examples": [
                # file-wo-widget:
                {
                    "displayOrder": 1,
                    "label": "Input files",
                    "description": "Files downloaded from service connected at the input",
                    "type": "data:*/*",
                },
                # v2
                {
                    "displayOrder": 2,
                    "label": "Sleep Time",
                    "description": "Time to wait before completion",
                    "type": "number",
                    "defaultValue": 0,
                    "unit": "second",
                    "widget": {"type": "TextArea", "details": {"minHeight": 3}},
                },
                # latest:
                {
                    "label": "Sleep Time",
                    "description": "Time to wait before completion",
                    "type": "number",
                    "defaultValue": 0,
                    "unit": "second",
                    "widget": {"type": "TextArea", "details": {"minHeight": 3}},
                },
            ],
        }


class ServiceOutput(ServiceProperty):
    widget: Optional[Widget] = Field(
        None,
        description="custom widget to use instead of the default one determined from the data-type",
        deprecated=True,
    )

    class Config(ServiceProperty.Config):
        schema_extra = {
            "examples": [
                # v1
                {
                    "displayOrder": 2,
                    "label": "Time Slept",
                    "description": "Time the service waited before completion",
                    "type": "number",
                },
                # v2
                {
                    "displayOrder": 2,
                    "label": "Time Slept",
                    "description": "Time the service waited before completion",
                    "type": "number",
                    "unit": "second",
                },
                # latest:
                {
                    "label": "Time Slept",
                    "description": "Time the service waited before completion",
                    "type": "number",
                    "unit": "second",
                },
            ]
        }


class ServiceKeyVersion(BaseModel):
    """This pair uniquely identifies a services"""

    key: str = Field(
        ...,
        description="distinctive name for the node based on the docker registry path",
        regex=KEY_RE,
        examples=[
            "simcore/services/comp/itis/sleeper",
            "simcore/services/dynamic/3dviewer",
        ],
    )
    version: str = Field(
        ...,
        description="service version number",
        regex=VERSION_RE,
        examples=["1.0.0", "0.0.1"],
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

    @validator("thumbnail", pre=True, always=False)
    @classmethod
    def validate_thumbnail(cls, value):  # pylint: disable=no-self-argument,no-self-use
        if value == "":
            return None
        return value


ServiceInputs = Dict[PropertyName, ServiceInput]
ServiceOutputs = Dict[PropertyName, ServiceOutput]


class ServiceDockerData(ServiceKeyVersion, ServiceCommonData):
    """
    Static metadata for a service injected in the image labels
    """

    integration_version: Optional[str] = Field(
        None,
        alias="integration-version",
        description="integration version number",
        regex=VERSION_RE,
        examples=["1.0.0"],
    )
    service_type: ServiceType = Field(
        ...,
        alias="type",
        description="service type",
        examples=["computational"],
    )

    badges: Optional[List[Badge]] = Field(None)

    authors: List[Author] = Field(..., min_items=1)
    contact: EmailStr = Field(
        ...,
        description="email to correspond to the authors about the node",
        examples=["lab@net.flix"],
    )
    inputs: Optional[ServiceInputs] = Field(
        ..., description="definition of the inputs of this node"
    )
    outputs: Optional[ServiceOutputs] = Field(
        ..., description="definition of the outputs of this node"
    )

    class Config:
        description = "Description of a simcore node 'class' with input and output"
        extra = Extra.forbid

        schema_extra = {
            "examples": [
                {
                    "name": "oSparc Python Runner",
                    "key": "simcore/services/comp/osparc-python-runner",
                    "type": "computational",
                    "integration-version": "1.0.0",
                    "version": "1.7.0",
                    "description": "oSparc Python Runner",
                    "contact": "smith@company.com",
                    "authors": [
                        {
                            "name": "John Smith",
                            "email": "smith@company.com",
                            "affiliation": "Company",
                        },
                        {
                            "name": "Richard Brown",
                            "email": "brown@uni.edu",
                            "affiliation": "University",
                        },
                    ],
                    "inputs": {
                        "input_1": {
                            "displayOrder": 1,
                            "label": "Input data",
                            "description": "Any code, requirements or data file",
                            "type": "data:*/*",
                        }
                    },
                    "outputs": {
                        "output_1": {
                            "displayOrder": 1,
                            "label": "Output data",
                            "description": "All data produced by the script is zipped as output_data.zip",
                            "type": "data:*/*",
                            "fileToKeyMap": {"output_data.zip": "output_1"},
                        }
                    },
                },
                # latest
                {
                    "name": "oSparc Python Runner",
                    "key": "simcore/services/comp/osparc-python-runner",
                    "type": "computational",
                    "integration-version": "1.0.0",
                    "version": "1.7.0",
                    "description": "oSparc Python Runner",
                    "contact": "smith@company.com",
                    "authors": [
                        {
                            "name": "John Smith",
                            "email": "smith@company.com",
                            "affiliation": "Company",
                        },
                        {
                            "name": "Richard Brown",
                            "email": "brown@uni.edu",
                            "affiliation": "University",
                        },
                    ],
                    "inputs": {
                        "input_1": {
                            "label": "Input data",
                            "description": "Any code, requirements or data file",
                            "type": "data:*/*",
                        }
                    },
                    "outputs": {
                        "output_1": {
                            "label": "Output data",
                            "description": "All data produced by the script is zipped as output_data.zip",
                            "type": "data:*/*",
                            "fileToKeyMap": {"output_data.zip": "output_1"},
                        }
                    },
                },
            ]
        }


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
    # Overrides all fields of ServiceCommonData:
    #    - for a partial update all members must be Optional
    #  FIXME: if API entry needs a schema to allow partial updates (e.g. patch/put),
    #        it should be implemented with a different model e.g. ServiceMetaDataUpdate
    #

    name: Optional[str]
    thumbnail: Optional[HttpUrl]
    description: Optional[str]

    # user-defined metatada
    classifiers: Optional[List[str]]
    quality: Dict[str, Any] = {}

    class Config:
        schema_extra = {
            "example": {
                "key": "simcore/services/dynamic/sim4life",
                "version": "1.0.9",
                "name": "sim4life",
                "description": "s4l web",
                "thumbnail": "http://thumbnailit.org/image",
                "quality": {
                    "enabled": True,
                    "tsr_target": {
                        f"r{n:02d}": {"level": 4, "references": ""}
                        for n in range(1, 11)
                    },
                    "annotations": {
                        "vandv": "",
                        "limitations": "",
                        "certificationLink": "",
                        "certificationStatus": "Uncertified",
                    },
                    "tsr_current": {
                        f"r{n:02d}": {"level": 0, "references": ""}
                        for n in range(1, 11)
                    },
                },
            }
        }


# -------------------------------------------------------------------
# Databases models
#  - table services_meta_data
#  - table services_access_rights


class ServiceMetaDataAtDB(ServiceKeyVersion, ServiceMetaData):
    # for a partial update all members must be Optional
    classifiers: Optional[List[str]] = Field([])
    owner: Optional[PositiveInt]

    class Config:
        orm_mode = True
        schema_extra = {
            "example": {
                "key": "simcore/services/dynamic/sim4life",
                "version": "1.0.9",
                "owner": 8,
                "name": "sim4life",
                "description": "s4l web",
                "thumbnail": "http://thumbnailit.org/image",
                "created": "2021-01-18 12:46:57.7315",
                "modified": "2021-01-19 12:45:00",
                "quality": {
                    "enabled": True,
                    "tsr_target": {
                        f"r{n:02d}": {"level": 4, "references": ""}
                        for n in range(1, 11)
                    },
                    "annotations": {
                        "vandv": "",
                        "limitations": "",
                        "certificationLink": "",
                        "certificationStatus": "Uncertified",
                    },
                    "tsr_current": {
                        f"r{n:02d}": {"level": 0, "references": ""}
                        for n in range(1, 11)
                    },
                },
            }
        }


class ServiceAccessRightsAtDB(ServiceKeyVersion, ServiceGroupAccessRights):
    gid: PositiveInt = Field(..., description="defines the group id", example=1)
    product_name: str = Field(
        ..., description="defines the product name", example="osparc"
    )

    class Config:
        orm_mode = True
        schema_extra = {
            "example": {
                "key": "simcore/services/dynamic/sim4life",
                "version": "1.0.9",
                "gid": 8,
                "execute_access": True,
                "write_access": True,
                "product_name": "osparc",
                "created": "2021-01-18 12:46:57.7315",
                "modified": "2021-01-19 12:45:00",
            }
        }
