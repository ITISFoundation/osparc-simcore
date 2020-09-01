"""
    Implements jsonschema api/specs/common/schemas/node-meta-v0.0.1.json

    Schema of metadata injected in docker image labels of services
"""

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, EmailStr, Field

from ..constants import SERVICE_IMAGE_NAME_RE, VERSION_RE


class Type(Enum):
    computational = "computational"
    dynamic = "dynamic"


class Badge(BaseModel):
    name: str = Field(
        ...,
        description="Name of the subject",
        example=["travis-ci", "coverals.io", "github.io"],
    )
    image: str = Field(
        ...,
        description="Url to the shield",
        example=[
            "https://travis-ci.org/ITISFoundation/osparc-simcore.svg?branch=master",
            "https://coveralls.io/repos/github/ITISFoundation/osparc-simcore/badge.svg?branch=master",
            "https://img.shields.io/website-up-down-green-red/https/itisfoundation.github.io.svg?label=documentation",
        ],
    )
    url: str = Field(
        ...,
        description="Link to status",
        example=[
            "https://travis-ci.org/ITISFoundation/osparc-simcore 'State of CI: build, test and pushing images'",
            "https://coveralls.io/github/ITISFoundation/osparc-simcore?branch=master 'Test coverage'",
            "https://itisfoundation.github.io/",
        ],
    )


class Author(BaseModel):
    name: str = Field(
        ..., description="Name of the author", example=["Sun Bak", "Delenn"]
    )
    email: EmailStr = Field(
        ...,
        description="Email address",
        example=["sun@sense.eight", "deleen@minbar.bab"],
    )
    affiliation: Optional[str] = Field(
        None, description="Affiliation of the author", example=["Sense8", "Babylon 5"]
    )


class ImageMetaData(BaseModel):
    key: str = Field(
        ...,
        description="distinctive name for the node based on the docker registry path",
        example=[
            "simcore/services/comp/itis/sleeper",
            "simcore/services/dynamic/3dviewer",
        ],
        regex=SERVICE_IMAGE_NAME_RE,
    )
    integration_version: Optional[str] = Field(
        None,
        alias="integration-version",
        description="integration version number",
        example=["1.0.0"],
        regex=VERSION_RE,
    )
    version: str = Field(
        ...,
        description="service version number",
        example=["1.0.0", "0.0.1"],
        regex=VERSION_RE,
    )
    _type: Type = Field(
        ..., alias="type", description="service type", example=["computational"]
    )
    name: str = Field(
        ...,
        description="short, human readable name for the node",
        example=["Fast Counter"],
    )
    thumbnail: Optional[str] = Field(
        None,
        description="url to the thumbnail",
        example=[
            "https://user-images.githubusercontent.com/32800795/61083844-ff48fb00-a42c-11e9-8e63-fa2d709c8baf.png"
        ],
    )
    badges: Optional[List[Badge]] = None
    description: str = Field(
        ...,
        description="human readable description of the purpose of the node",
        example=[
            "Our best node type",
            "The mother of all nodes, makes your numbers shine!",
        ],
    )
    authors: List[Author]
    contact: EmailStr = Field(
        ...,
        description="email to correspond to the authors about the node",
        example=["lab@net.flix"],
    )
    inputs: Dict[str, Any] = Field(
        ..., description="definition of the inputs of this node"
    )
    outputs: Dict[str, Any] = Field(
        ..., description="definition of the outputs of this node"
    )
