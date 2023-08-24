import re
from datetime import datetime
from enum import Enum
from typing import Any, ClassVar, Final, TypeAlias
from uuid import uuid4

import arrow
from pydantic import (
    BaseModel,
    ConstrainedStr,
    Extra,
    Field,
    HttpUrl,
    NonNegativeInt,
    StrictBool,
    StrictFloat,
    StrictInt,
    validator,
)

from .basic_regex import VERSION_RE
from .boot_options import BootOption, BootOptions
from .emails import LowerCaseEmailStr
from .services_constants import FILENAME_RE, PROPERTY_TYPE_RE
from .services_ui import Widget
from .utils.json_schema import (
    InvalidJsonSchema,
    any_ref_key,
    jsonschema_validate_schema,
)

# CONSTANTS -------------------------------------------
# NOTE: move to _constants.py: SEE https://github.com/ITISFoundation/osparc-simcore/issues/3486

# e.g. simcore/services/comp/opencor
SERVICE_KEY_RE: Final[re.Pattern[str]] = re.compile(
    r"^simcore/services/"
    r"(?P<type>(comp|dynamic|frontend))/"
    r"(?P<subdir>[a-z0-9][a-z0-9_.-]*/)*"
    r"(?P<name>[a-z0-9-_]+[a-z0-9])$"
)
# e.g. simcore%2Fservices%2Fcomp%2Fopencor
SERVICE_ENCODED_KEY_RE: Final[re.Pattern[str]] = re.compile(
    r"^simcore%2Fservices%2F"
    r"(?P<type>(comp|dynamic|frontend))%2F"
    r"(?P<subdir>[a-z0-9][a-z0-9_.-]*%2F)*"
    r"(?P<name>[a-z0-9-_]+[a-z0-9])$"
)

DYNAMIC_SERVICE_KEY_RE = re.compile(
    r"^simcore/services/dynamic/"
    r"(?P<subdir>[a-z0-9][a-z0-9_.-]*/)*"
    r"(?P<name>[a-z0-9-_]+[a-z0-9])$"
)
DYNAMIC_SERVICE_KEY_FORMAT = "simcore/services/dynamic/{service_name}"

COMPUTATIONAL_SERVICE_KEY_RE = re.compile(
    r"^simcore/services/comp/"
    r"(?P<subdir>[a-z0-9][a-z0-9_.-]*/)*"
    r"(?P<name>[a-z0-9-_]+[a-z0-9])$"
)
COMPUTATIONAL_SERVICE_KEY_FORMAT = "simcore/services/comp/{service_name}"

PROPERTY_KEY_RE = r"^[-_a-zA-Z0-9]+$"  # TODO: PC->* it would be advisable to have this "variable friendly" (see VARIABLE_NAME_RE)

LATEST_INTEGRATION_VERSION = "1.0.0"


# CONSTRAINT TYPES -------------------------------------------
class ServicePortKey(ConstrainedStr):
    regex = re.compile(PROPERTY_KEY_RE)

    class Config:
        frozen = True


class FileName(ConstrainedStr):
    regex = re.compile(FILENAME_RE)

    class Config:
        frozen = True


class ServiceKey(ConstrainedStr):
    regex = SERVICE_KEY_RE

    class Config:
        frozen = True


class ServiceKeyEncoded(ConstrainedStr):
    regex = re.compile(SERVICE_ENCODED_KEY_RE)

    class Config:
        frozen = True


class DynamicServiceKey(ServiceKey):
    regex = DYNAMIC_SERVICE_KEY_RE


class ComputationalServiceKey(ServiceKey):
    regex = COMPUTATIONAL_SERVICE_KEY_RE


class ServiceVersion(ConstrainedStr):
    regex = re.compile(VERSION_RE)

    class Config:
        frozen = True


class RunID(str):
    """
    Used to assign a unique identifier to the run of a service.

    Example usage:
    The dynamic-sidecar uses this to distinguish between current
    and old volumes for different runs.
    Avoids overwriting data that left dropped on the node (due to an error)
    and gives the osparc-agent an opportunity to back it up.
    """

    __slots__ = ()

    @classmethod
    def create(cls) -> "RunID":
        # NOTE: there was a legacy version of this RunID
        # legacy version:
        #   '0ac3ed64-665b-42d2-95f7-e59e0db34242'
        # current version:
        #   '1690203099_0ac3ed64-665b-42d2-95f7-e59e0db34242'
        utc_int_timestamp: int = arrow.utcnow().int_timestamp
        run_id_format = f"{utc_int_timestamp}_{uuid4()}"
        return cls(run_id_format)


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
    email: LowerCaseEmailStr = Field(
        ...,
        examples=["sun@sense.eight", "deleen@minbar.bab"],
        description="Email address",
    )
    affiliation: str | None = Field(
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
    display_order: float | None = Field(
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

    content_schema: dict[str, Any] | None = Field(
        None,
        description="jsonschema of this input/output. Required when type='ref_contentSchema'",
        alias="contentSchema",
    )

    # value
    file_to_key_map: dict[FileName, ServicePortKey] | None = Field(
        None,
        alias="fileToKeyMap",
        description="Place the data associated with the named keys in files",
        examples=[{"dir/input1.txt": "key_1", "dir33/input2.txt": "key2"}],
    )

    # TODO: should deprecate since content_schema include units
    unit: str | None = Field(
        None,
        description="Units, when it refers to a physical quantity",
    )

    class Config:
        extra = Extra.forbid

    @validator("content_schema")
    @classmethod
    def check_type_is_set_to_schema(cls, v, values):
        if v is not None and (ptype := values["property_type"]) != "ref_contentSchema":
            msg = f"content_schema is defined but set the wrong type.Expected type=ref_contentSchema but got ={ptype}."
            raise ValueError(msg)
        return v

    @validator("content_schema")
    @classmethod
    def check_valid_json_schema(cls, v):
        if v is not None:
            try:
                jsonschema_validate_schema(schema=v)

                if any_ref_key(v):
                    # SEE https://github.com/ITISFoundation/osparc-simcore/issues/3030
                    msg = "Schemas with $ref are still not supported"
                    raise ValueError(msg)

            except InvalidJsonSchema as err:
                failed_path = "->".join(map(str, err.path))
                msg = f"Invalid json-schema at {failed_path}: {err.message}"
                raise ValueError(msg) from err
        return v

    @classmethod
    def _from_json_schema_base_implementation(
        cls, port_schema: dict[str, Any]
    ) -> dict[str, Any]:
        description = port_schema.pop("description", port_schema["title"])
        return {
            "label": port_schema["title"],
            "description": description,
            "type": "ref_contentSchema",
            "contentSchema": port_schema,
        }


class ServiceInput(BaseServiceIOModel):
    """
    Metadata on a service input port
    """

    # TODO: should deprecate since content_schema include defaults as well
    default_value: StrictBool | StrictInt | StrictFloat | str | None = Field(
        None, alias="defaultValue", examples=["Dog", True]
    )

    widget: Widget | None = Field(
        None,
        description="custom widget to use instead of the default one determined from the data-type",
    )

    class Config(BaseServiceIOModel.Config):
        schema_extra: ClassVar[dict[str, Any]] = {
            "examples": [
                # file-wo-widget:
                {
                    "displayOrder": 1,
                    "label": "Input files - file-wo-widget",
                    "description": "Files downloaded from service connected at the input",
                    "type": "data:*/*",
                },
                # v2
                {
                    "displayOrder": 2,
                    "label": "Sleep Time - v2",
                    "description": "Time to wait before completion",
                    "type": "number",
                    "defaultValue": 0,
                    "unit": "second",
                    "widget": {"type": "TextArea", "details": {"minHeight": 3}},
                },
                # latest:
                {
                    "label": "Sleep Time - latest",
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

    @classmethod
    def from_json_schema(cls, port_schema: dict[str, Any]) -> "ServiceInput":
        """Creates input port model from a json-schema"""
        data = cls._from_json_schema_base_implementation(port_schema)
        return cls.parse_obj(data)


class ServiceOutput(BaseServiceIOModel):
    widget: Widget | None = Field(
        None,
        description="custom widget to use instead of the default one determined from the data-type",
        deprecated=True,
    )

    class Config(BaseServiceIOModel.Config):
        schema_extra: ClassVar[dict[str, Any]] = {
            "examples": [
                {
                    "displayOrder": 2,
                    "label": "Time Slept",
                    "description": "Time the service waited before completion",
                    "type": "number",
                },
                {
                    "displayOrder": 2,
                    "label": "Time Slept - units",
                    "description": "Time the service waited before completion",
                    "type": "number",
                    "unit": "second",
                },
                {
                    "label": "Time Slept - w/o displayorder",
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

    @classmethod
    def from_json_schema(cls, port_schema: dict[str, Any]) -> "ServiceOutput":
        """Creates output port model from a json-schema"""
        data = cls._from_json_schema_base_implementation(port_schema)
        return cls.parse_obj(data)


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


class _BaseServiceCommonDataModel(BaseModel):
    name: str = Field(
        ...,
        description="short, human readable name for the node",
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

    @validator("thumbnail", pre=True, always=False)
    @classmethod
    def validate_thumbnail(cls, value):  # pylint: disable=no-self-argument,no-self-use
        if value == "":
            return None
        return value


ServiceInputsDict: TypeAlias = dict[ServicePortKey, ServiceInput]
ServiceOutputsDict: TypeAlias = dict[ServicePortKey, ServiceOutput]


class ServiceDockerData(ServiceKeyVersion, _BaseServiceCommonDataModel):
    """
    Static metadata for a service injected in the image labels

    This is one to one with node-meta-v0.0.1.json
    """

    integration_version: str | None = Field(
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

    badges: list[Badge] | None = Field(None)

    authors: list[Author] = Field(..., min_items=1)
    contact: LowerCaseEmailStr = Field(
        ...,
        description="email to correspond to the authors about the node",
        examples=["lab@net.flix"],
    )
    inputs: ServiceInputsDict | None = Field(
        ..., description="definition of the inputs of this node"
    )
    outputs: ServiceOutputsDict | None = Field(
        ..., description="definition of the outputs of this node"
    )

    boot_options: BootOptions | None = Field(
        None,
        alias="boot-options",
        description="Service defined boot options. These get injected in the service as env variables.",
    )
    min_visible_inputs: NonNegativeInt | None = Field(
        None,
        alias="min-visible-inputs",
        description=(
            "The number of 'data type inputs' displayed by default in the UI. "
            "When None all 'data type inputs' are displayed."
        ),
    )

    class Config:
        description = "Description of a simcore node 'class' with input and output"
        extra = Extra.forbid
        frozen = False  # it inherits from ServiceKeyVersion.

        schema_extra: ClassVar[dict[str, Any]] = {
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
                    "description": "oSparc Python Runner with boot options",
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
                    "min-visible-inputs": 2,
                },
            ]
        }


class ServiceMetaData(_BaseServiceCommonDataModel):
    # Overrides all fields of _BaseServiceCommonDataModel:
    #    - for a partial update all members must be Optional
    #  FIXME: if API entry needs a schema to allow partial updates (e.g. patch/put),
    #        it should be implemented with a different model e.g. ServiceMetaDataUpdate
    #

    name: str | None
    thumbnail: HttpUrl | None
    description: str | None
    deprecated: datetime | None = Field(
        default=None,
        description="If filled with a date, then the service is to be deprecated at that date (e.g. cannot start anymore)",
    )

    # user-defined metatada
    classifiers: list[str] | None
    quality: dict[str, Any] = {}

    class Config:
        schema_extra: ClassVar[dict[str, Any]] = {
            "example": {
                "key": "simcore/services/dynamic/sim4life",
                "version": "1.0.9",
                "name": "sim4life",
                "description": "s4l web",
                "thumbnail": "https://thumbnailit.org/image",
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
