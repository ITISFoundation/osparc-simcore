import sys
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, EmailStr, Field, HttpUrl, constr
from pydantic.types import ConstrainedStr

current_file = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve()

KEY_RE = r"^(simcore)/(services)/(comp|dynamic|frontend)(/[^\s]+)+$"
VERSION_RE = r"^(0|[1-9]\d*)(\.(0|[1-9]\d*)){2}(-(0|[1-9]\d*|\d*[-a-zA-Z][-\da-zA-Z]*)(\.(0|[1-9]\d*|\d*[-a-zA-Z][-\da-zA-Z]*))*)?(\+[-\da-zA-Z]+(\.[-\da-zA-Z-]+)*)?$"
INPUT_NAME_RE = r"^[-_a-zA-Z0-9]+$"
PROPERTY_TYPE_RE = r"^(number|integer|boolean|string|data:([^/\s,]+/[^/\s,]+|\[[^/\s,]+/[^/\s,]+(,[^/\s]+/[^/,\s]+)*\]))$"


class ServiceType(Enum):
    computational = "computational"
    dynamic = "dynamic"


class ServiceBadge(BaseModel):
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


class ServiceAuthor(BaseModel):
    name: str = Field(..., description="Name of the author", example="Jim Knopf")
    email: EmailStr = Field(
        ...,
        example=["sun@sense.eight", "deleen@minbar.bab"],
        description="Email address",
    )
    affiliation: str = Field(
        ..., example=["Sense8", "Babylon 5"], description="Affiliation of the author"
    )

class FileToKeyMap(BaseModel):
    

class ServiceProperty(BaseModel):
    display_order: int = Field(
        ...,
        description="use this to numerically sort the properties for display",
        example=1,
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
    file_to_key_map: 


class Service(BaseModel):
    key: constr(regex=KEY_RE) = Field(
        ...,
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
    integration_version: constr(regex=VERSION_RE) = Field(
        ...,
        description="service oSparc integration version number",
        # regex=VERSION_RE,
        example="1.0.0",
    )
    service_type: str = Field(
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
    badges: Optional[List[ServiceBadge]] = Field(None)
    description: str = Field(
        ...,
        description="human readable description of the purpose of the node",
        example=[
            "Our best node type",
            "The mother of all nodes, makes your numbers shine!",
        ],
    )
    authors: List[ServiceAuthor]
    contact: EmailStr = Field(
        ...,
        description="email to correspond to the authors about the node",
        example=["lab@net.flix"],
    )
    inputs: Optional[Dict[str, Any]] = Field(
        None, description="all the input configurable for this service"
    )
    outputs: Optional[Dict[str, Any]] = Field(
        None, description="all the output configurable for this service"
    )


if __name__ == "__main__":

    with open(current_file.with_suffix(".json"), "wt") as fh:
        print(Service.schema_json(indent=2), file=fh)
