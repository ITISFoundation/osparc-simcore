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

from .basic_regex import VERSION_RE
from .boot_options import BootOption, BootOptions
from .services_ui import Widget

# CONSTANTS -------------------------------------------

# NOTE: needs to end with / !!
SERVICE_KEY_RE = r"^(simcore)/(services)/(comp|dynamic|frontend)(/[\w/-]+)+$"

DYNAMIC_SERVICE_KEY_RE = r"^(simcore)/(services)/dynamic(/[\w/-]+)+$"
DYNAMIC_SERVICE_KEY_FORMAT = "simcore/services/dynamic/{service_name}"

COMPUTATIONAL_SERVICE_KEY_RE = r"^(simcore)/(services)/comp(/[\w/-]+)+$"
COMPUTATIONAL_SERVICE_KEY_FORMAT = "simcore/services/comp/{service_name}"

KEY_RE = SERVICE_KEY_RE  # TODO: deprecate this global constant by SERVICE_KEY_RE

SERVICE_NETWORK_RE = r"^([a-zA-Z0-9_-]+)$"


PROPERTY_TYPE_RE = r"^(number|integer|boolean|string|ref_contentSchema|data:([^/\s,]+/[^/\s,]+|\[[^/\s,]+/[^/\s,]+(,[^/\s]+/[^/,\s]+)*\]))$"
PROPERTY_KEY_RE = r"^[-_a-zA-Z0-9]+$"  # TODO: PC->* it would be advisable to have this "variable friendly" (see VARIABLE_NAME_RE)

FILENAME_RE = r".+"

LATEST_INTEGRATION_VERSION = "1.0.0"

# CONSTRAINT TYPES -------------------------------------------

PropertyName = constr(regex=PROPERTY_KEY_RE)
FileName = constr(regex=FILENAME_RE)

ServiceKey = constr(regex=KEY_RE)
ServiceVersion = constr(regex=VERSION_RE)


class ServiceType(str, Enum):
    COMPUTATIONAL = "computational"
    DYNAMIC = "dynamic"
    FRONTEND = "frontend"
    BACKEND = "backend"


# TODO: create a flags enum that accounts for every column
#
# | service name    | defininition | implementation | runs                    | ``ServiceType``               |                 |
# | --------------- | ------------ | -------------- | ----------------------- | ----------------------------- | --------------- |
# | ``file-picker`` | BE           | FE             | FE                      | ``ServiceType.FRONTEND``      | function        |
# | ``isolve``      | DI-labels    | DI             | Dask-BE (own container) | ``ServiceType.COMPUTATIONAL`` | container       |
# | ``jupyter-*``   | DI-labels    | DI             | DySC-BE (own container) | ``ServiceType.DYNAMIC``       | container       |
# | ``iterator-*``  | BE           | BE             | BE    (webserver)       | ``ServiceType.BACKEND``       | function        |
# | ``pyfun-*``     | BE           | BE             | Dask-BE  (dask-sidecar) | ``ServiceType.COMPUTATIONAL`` | function        |
#
#
# where FE (front-end), DI (docker image), Dask/DySC (dask/dynamic sidecar), BE (backend).


# MODELS -------------------------------------------
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


class BaseServiceIOModel(BaseModel):
    """
    Base class for service input/outputs
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

    content_schema: Optional[Dict[str, Any]] = Field(
        None,
        description="jsonschema of this input/output. Required when type='ref_contentSchema'",
        alias="contentSchema",
    )

    # value
    file_to_key_map: Optional[Dict[FileName, PropertyName]] = Field(
        None,
        alias="fileToKeyMap",
        description="Place the data associated with the named keys in files",
        examples=[{"dir/input1.txt": "key_1", "dir33/input2.txt": "key2"}],
    )

    # TODO: use discriminators
    # TODO: deprecate
    unit: Optional[str] = Field(
        None, description="Units, when it refers to a physical quantity"
    )

    class Config:
        extra = Extra.forbid
        # TODO: all alias with camecase

    @validator("content_schema")
    @classmethod
    def check_type_is_set_to_schema(cls, v, values):
        # TODO: content_schema should be a valid json-schema
        #
        if v is not None and (ptype := values["property_type"]) != "ref_contentSchema":
            raise ValueError(
                "content_schema is defined but set the wrong type."
                f"Expected type=ref_contentSchema but got ={ptype}."
            )

        # TODO:  Check is a valid jsonschema? Use $ref to or active validation as in
        # import jsonschema
        # try:
        #   jsonschema.validate({}, v)
        # except SchemaError as err:
        #   raise ValueError()
        # except jsonschema.ValidationError as err:
        #

        return v


class ServiceInput(BaseServiceIOModel):
    """
    Metadata on a service input port
    """

    # NOTE: should deprecate since schema include defaults as well
    default_value: Optional[Union[StrictBool, StrictInt, StrictFloat, str]] = Field(
        None, alias="defaultValue", examples=["Dog", True]
    )

    widget: Optional[Widget] = Field(
        None,
        description="custom widget to use instead of the default one determined from the data-type",
    )

    class Config(BaseServiceIOModel.Config):
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
                {
                    "label": "array_numbers",
                    "description": "Some array of numbers",
                    "type": "ref_contentSchema",
                    "contentSchema": {
                        "title": "list[number]",
                        "type": "array",
                        "items": {"type": "number"},
                    },
                },
                {
                    "label": "my_object",
                    "description": "Some object",
                    "type": "ref_contentSchema",
                    "contentSchema": {
                        "title": "an object named A",
                        "type": "object",
                        "properties": {
                            "i": {"title": "Int", "type": "integer", "default": 3},
                            "b": {"title": "Bool", "type": "boolean"},
                            "s": {"title": "Str", "type": "string"},
                        },
                        "required": ["b", "s"],
                    },
                },
            ],
        }


class ServiceOutput(BaseServiceIOModel):
    widget: Optional[Widget] = Field(
        None,
        description="custom widget to use instead of the default one determined from the data-type",
        deprecated=True,
    )

    class Config(BaseServiceIOModel.Config):
        schema_extra = {
            "examples": [
                {
                    "displayOrder": 2,
                    "label": "Time Slept",
                    "description": "Time the service waited before completion",
                    "type": "number",
                },
                {
                    "displayOrder": 2,
                    "label": "Time Slept",
                    "description": "Time the service waited before completion",
                    "type": "number",
                    "unit": "second",
                },
                {
                    "label": "Time Slept",
                    "description": "Time the service waited before completion",
                    "type": "number",
                    "unit": "second",
                },
                {
                    "label": "Output file 1",
                    "displayOrder": 4.0,
                    "description": "Output file uploaded from the outputs folder",
                    "type": "data:*/*",
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


class _BaseServiceCommonDataModel(BaseModel):
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


class ServiceDockerData(ServiceKeyVersion, _BaseServiceCommonDataModel):
    """
    Static metadata for a service injected in the image labels

    This is one to one with node-meta-v0.0.1.json
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

    boot_options: Optional[BootOptions] = Field(
        None,
        alias="boot-options",
        description="Service defined boot options. These get injected in the service as env variables.",
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
                    "boot-options": {
                        "example_service_defined_boot_mode": BootOption.Config.schema_extra[
                            "examples"
                        ][
                            0
                        ],
                        "example_service_defined_theme_selection": BootOption.Config.schema_extra[
                            "examples"
                        ][
                            1
                        ],
                    },
                },
            ]
        }


class ServiceMetaData(_BaseServiceCommonDataModel):
    # Overrides all fields of _BaseServiceCommonDataModel:
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
