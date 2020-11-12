import re
from datetime import datetime
from enum import Enum
from typing import List, Optional, Union
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl, confloat, constr

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
            **kwargs
        )


class Job(BaseModel):
    job_id: UUID
    inputs_sha: str
    status_url: HttpUrl
    results_url: HttpUrl


# TODO: these need to be in sync with celery task states
class TaskStates(str, Enum):
    UNDEFINED = "undefined"
    PENDING = "pending"
    JOBNING = "jobning"
    SUCCESS = "success"
    FAILED = "failed"


class JobState(BaseModel):
    status: TaskStates = TaskStates.UNDEFINED
    progress: int = confloat(ge=0, le=100)
    started_at: datetime
    stopped_at: Union[datetime, None] = None


class SolverInput(BaseModel):
    key: KeyIdentifier
    content_type: str
    title: Optional[str] = None


class JobInput(SolverInput):
    value: Union[float, str, int, None] = None
    value_url: Optional[HttpUrl] = None

    # TODO: validate one or the other but not both


class SolverOutput(BaseModel):
    content_type: str
    key: KeyIdentifier
    title: Optional[str] = None


class JobOutput(SolverOutput):
    status: TaskStates = TaskStates.UNDEFINED  # every output can
    value: Optional[Union[float, str, int]] = None
    value_url: Optional[HttpUrl] = None
