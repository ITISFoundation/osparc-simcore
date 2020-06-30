from enum import Enum
from typing import Dict, List, Optional, Union

from pydantic import BaseModel, url_regex, Field, EmailStr

KEY_RE = r"^(simcore)/(services)/(comp|dynamic|frontend)(/[^\s]+)+$"
VERSION_RE = r"^(0|[1-9]\d*)(\.(0|[1-9]\d*)){2}(-(0|[1-9]\d*|\d*[-a-zA-Z][-\da-zA-Z]*)(\.(0|[1-9]\d*|\d*[-a-zA-Z][-\da-zA-Z]*))*)?(\+[-\da-zA-Z]+(\.[-\da-zA-Z-]+)*)?$"
INPUT_RE = r"^[-_a-zA-Z0-9]+$"

class ServiceTypeEnum(str, Enum):
    Computational = "computational"
    Dynamic = "dynamic"


class ServiceBadge(BaseModel):
    name: str = Field(..., description="Name of the subject", example="github.io")
    image: str = Field(
        ...,
        description="Url to the badge",
        regex=url_regex,
        example="https://coveralls.io/repos/github/ITISFoundation/osparc-simcore/badge.svg?branch=master",
    )
    url: str = Field(
        ...,
        description="Link to the status",
        regex=url_regex,
        example="https://itisfoundation.github.io/",
    )


class ServiceAuthor(BaseModel):
    name: str = Field(..., description="Name of the author", example="Jim Knopf")
    email: EmailStr = Field(...,)
    affiliation: str = Field(
        ..., description="Affiliation of the author", example="The University"
    )

class ServiceInput(BaseModel):



class Service(BaseModel):
    key: str = Field(
        ...,
        description="distinctive name for the node based on the docker registry path",
        regex=KEY_RE,
        example="simcore/services/comp/itis/sleeper",
    )
    version: str = Field(
        ..., description="service version number", regex=VERSION_RE, example="2.3.45"
    )
    integration_version: str = Field(
        ...,
        description="service oSparc integration version number",
        regex=VERSION_RE,
        example="1.0.0",
    )
    service_type: str = Field(
        ...,
        title="type",
        description="service type",
        enum=ServiceTypeEnum,
        example="computational",
    )
    name: str = Field(
        ...,
        description="short, human readable name for the node",
        example="Fast Counter",
    )
    thumbnail: Optional[str] = Field(
        None,
        description="url to the thumbnail",
        regex=url_regex,
        example="https://user-images.githubusercontent.com/32800795/61083844-ff48fb00-a42c-11e9-8e63-fa2d709c8baf.png",
    )
    badges: Optional[List[ServiceBadge]] = Field(None)
    description: str = Field(
        ...,
        description="human readable description of the purpose of the node",
        example="The mother of all nodes, makes your numbers shine!",
    )
    authors: List[ServiceAuthor]
    contact: EmailStr = Field(
        ..., description="email to correspond to the authors about the node"
    )
    inputs: Optional[Dict[str, InputTypes]] = Field(None, description="all the input configurable for this service")
    outputs: Optional[Dict[str, OutputTypes]] = Field(None, description="all the output configurable for this service")
