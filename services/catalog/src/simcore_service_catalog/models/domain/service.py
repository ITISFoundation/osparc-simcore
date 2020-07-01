import sys
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Type, Union

from pydantic import BaseModel, EmailStr, Extra, Field, FilePath, HttpUrl, constr
from pydantic.schema import schema
from pydantic.types import ConstrainedInt, ConstrainedStr, PositiveInt, StrictBool

current_file = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve()

KEY_RE = r"^(simcore)/(services)/(comp|dynamic)(/[^\s]+)+$"
VERSION_RE = r"^(0|[1-9]\d*)(\.(0|[1-9]\d*)){2}(-(0|[1-9]\d*|\d*[-a-zA-Z][-\da-zA-Z]*)(\.(0|[1-9]\d*|\d*[-a-zA-Z][-\da-zA-Z]*))*)?(\+[-\da-zA-Z]+(\.[-\da-zA-Z-]+)*)?$"
PROPERTY_TYPE_RE = r"^(number|integer|boolean|string|data:([^/\s,]+/[^/\s,]+|\[[^/\s,]+/[^/\s,]+(,[^/\s]+/[^/,\s]+)*\]))$"

PROPERTY_KEY_RE = r"^[-_a-zA-Z0-9]+$"
FILENAME_RE = r".+"

PropertyName = constr(regex=PROPERTY_KEY_RE)
FileName = constr(regex=FILENAME_RE)


class ServiceType(str, Enum):
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

        @staticmethod
        def schema_extra(schema: Dict[str, Any], model: Type) -> None:
            # remove the title of properties
            for prop in schema.get("properties", {}).values():
                prop.pop("title", None)


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

        @staticmethod
        def schema_extra(schema: Dict[str, Any], model: Type) -> None:
            # remove the title of properties
            for prop in schema.get("properties", {}).values():
                prop.pop("title", None)


class WidgetType(str, Enum):
    TextArea = "TextArea"
    SelectBox = "SelectBox"


class TextArea(BaseModel):
    min_height: PositiveInt = Field(
        ..., alias="minHeight", description="minimum Height of the textarea"
    )

    class Config:
        extra = Extra.forbid

        @staticmethod
        def schema_extra(schema: Dict[str, Any], model: Type) -> None:
            # remove the title of properties
            for prop in schema.get("properties", {}).values():
                prop.pop("title", None)


class Structure(BaseModel):
    key: Union[str, bool, float]
    label: str

    class Config:
        extra = Extra.forbid

        @staticmethod
        def schema_extra(schema: Dict[str, Any], model: Type) -> None:
            # remove the title of properties
            for prop in schema.get("properties", {}).values():
                prop.pop("title", None)


class SelectBox(BaseModel):
    structure: List[Structure] = Field(..., min_items=1)

    class Config:
        extra = Extra.forbid

        @staticmethod
        def schema_extra(schema: Dict[str, Any], model: Type) -> None:
            # remove the title of properties
            for prop in schema.get("properties", {}).values():
                prop.pop("title", None)


class Widget(BaseModel):
    widget_type: WidgetType = Field(
        ..., alias="type", description="type of the property"
    )
    details: Union[TextArea, SelectBox]

    class Config:
        extra = Extra.forbid

        @staticmethod
        def schema_extra(schema: Dict[str, Any], model: Type) -> None:
            # remove the title of properties
            for prop in schema.get("properties", {}).values():
                prop.pop("title", None)


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

        @staticmethod
        def schema_extra(schema: Dict[str, Any], model: Type) -> None:
            # remove the title of properties
            for prop in schema.get("properties", {}).values():
                prop.pop("title", None)


class ServiceInput(ServiceProperty):
    widget: Optional[Widget] = Field(
        None,
        description="custom widget to use instead of the default one determined from the data-type",
    )


class ServiceData(BaseModel):
    key: constr(regex=KEY_RE) = Field(
        ...,
        title="",
        description="distinctive name for the node based on the docker registry path",
        # regex=KEY_RE,
        example=[
            "simcore/services/comp/itis/sleeper",
            "simcore/services/dynamic/3dviewer",
        ],
    )
    version: constr(regex=VERSION_RE) = Field(
        ...,
        description="service version number",
        # regex=VERSION_RE,
        example=["1.0.0", "0.0.1"],
    )
    integration_version: Optional[constr(regex=VERSION_RE)] = Field(
        None,
        alias="integration-version",
        description="service oSparc integration version number",
        # regex=VERSION_RE,
        example="1.0.0",
    )
    service_type: ServiceType = Field(
        ..., alias="type", description="service type", example="computational",
    )
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
    badges: Optional[List[Badge]] = Field(None)
    description: str = Field(
        ...,
        description="human readable description of the purpose of the node",
        example=[
            "Our best node type",
            "The mother of all nodes, makes your numbers shine!",
        ],
    )
    authors: List[Author] = Field(..., min_items=1)
    contact: EmailStr = Field(
        ...,
        description="email to correspond to the authors about the node",
        example=["lab@net.flix"],
    )
    inputs: Optional[Dict[PropertyName, ServiceInput]] = Field(
        ..., description="all the input configurable for this service"
    )
    outputs: Optional[Dict[PropertyName, ServiceProperty]] = Field(
        ..., description="all the output configurable for this service"
    )

    class Config:
        description = "Description of a simcore node 'class' with input and output"
        title = "simcore node"
        extra = Extra.forbid

        @staticmethod
        def schema_extra(schema: Dict[str, Any], model: Type) -> None:
            # remove the title of properties
            for prop in schema.get("properties", {}).values():
                prop.pop("title", None)


if __name__ == "__main__":

    with open(current_file.with_suffix(".json"), "wt") as fh:
        print(ServiceData.schema_json(indent=2), file=fh)
