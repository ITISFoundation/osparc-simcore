import re
from datetime import datetime
from enum import Enum
from typing import List, Optional, Union
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl, conint, constr

LATEST_VERSION = "latest"
KEY_RE = r"^(simcore)/(services)/(comp)(/[^\s/]+)+$"  # NOTE: needs to end with / !!


# Human-readable unique identifier
KeyIdentifier = constr(strip_whitespace=True, min_length=3)
SolverImageName = constr(regex=KEY_RE, strip_whitespace=True)


class SolverImage(BaseModel):
    # This is an image. Notice that tags refer to this image
    uuid: UUID = Field(..., description="Image sha256 unique identifier")
    name: SolverImageName = Field(
        ...,
        description="Name of the solver image including namespace and excluding tag",
    )
    maintainer: str
    released: datetime


class Solver(BaseModel):
    """A released solver with a specific version

    This version might have human-readable alias (e.g. latest) or
    hierarchical version tags (e.g. 3, 3.2)
    """

    uuid: UUID = Field(..., description="Same as the solver's image sha256")
    name: str = Field(..., description="Image name including namespace")
    version: str  # complete tag.  e.g. 3.4.5 TODO: regex for version in python PEP
    version_aliases: List[str] = []  # remaining tags

    title: str
    description: Optional[str]
    maintainer: str
    released: Optional[datetime]  # TODO: turn into required

    solver_url: HttpUrl

    @classmethod
    def create_from_image(cls, img: SolverImage, tags: List, **kwargs) -> "Solver":
        version = None
        alias = []
        for tag in tags:
            if re.match(r"\d+\.\d+\.\d+", tag):
                version = tag
            else:
                alias.append(tag)

        return cls(
            uuid=img.uuid,
            name=img.name,
            title=img.name.split("/")[-1],
            maintainer=img.maintainer,
            released=img.released,
            version=version,
            version_aliases=alias,
            **kwargs,
        )


# TODO: this might be in common with Director-v2 models
class Job(BaseModel):
    job_id: UUID
    inputs_sha: str
    solver_id: UUID

    # hyperlinks
    solver_url: HttpUrl
    inspect_url: HttpUrl
    outputs_url: HttpUrl


# TODO: these need to be in sync with celery task states
class TaskStates(str, Enum):
    UNDEFINED = "undefined"
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class JobStatus(BaseModel):
    """

    NOTE About naming. The result of an inspection on X returns a Status object
        What is the status of X? What sort of state is X in?
        SEE https://english.stackexchange.com/questions/12958/status-vs-state
    """

    job_id: UUID
    state: TaskStates
    progress: conint(ge=0, le=100) = 0

    # Timestamps to some of the states
    # TODO: sync state events and timestamps
    submitted_at: datetime
    started_at: Optional[datetime] = Field(
        None,
        description="Timestamp that indicate the moment the solver starts execution or None if the event did not occur",
    )
    stopped_at: Optional[datetime] = Field(
        None,
        description="Timestamp at which the solver finished or killed execution or None if the event did not occur",
    )

    def timestamp(self, event: str = "submitted"):
        setattr(self, f"{event}_at", datetime.utcnow())


class SolverPort(BaseModel):
    name: KeyIdentifier = Field(
        ...,
        description="Name given to the input/output in solver specs (see solver metadata.yml)",
    )

    # TODO: define more specifically
    #   - api/specs/common/schemas/node-meta-v0.0.1.json
    #   - http://www.iana.org/assignments/media-types/media-types.xhtml
    type: constr(
        strict=True,
        regex=r"^(number|integer|boolean|string|data:([^/\s,]+/[^/\s,]+|\[[^/\s,]+/[^/\s,]+(,[^/\s]+/[^/,\s]+)*\]))$",
    ) = Field(None, description="Data type expected on this input/ouput")

    title: Optional[str] = Field(
        None, description="Short human readable name to identify input/output"
    )


class JobInput(SolverPort):
    value: Union[float, str, int, HttpUrl, None] = None

    # TODO: validate one or the other but not both

    class Config:
        schema_extra = {
            "example": {
                "name": "T",
                "content_type": "number",
                "title": "Temperature",
                "value": "33",
            }
        }


class JobOutput(SolverPort):
    status: TaskStates = Field(
        ..., description="State towards completion of this output"
    )
    value: Union[float, str, int, HttpUrl, None] = Field(
        ..., description="Result value in this output"
    )

    # TODO: ???
    class Config:
        schema_extra = {
            "example": {
                "name": "SAR",
                "content_type": "data:application/hdf5",
                "title": "SAR field output file",
                "value": "1dc2b1e6-a139-47ad-9e0c-b7b791cd4d7a",
            }
        }
