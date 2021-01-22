import functools
from datetime import datetime
from enum import Enum
from typing import Optional, Union
from uuid import UUID, uuid3

from models_library.basic_regex import VERSION_RE
from models_library.services import COMPUTATIONAL_SERVICE_KEY_RE, ServiceDockerData
from pydantic import BaseModel, Field, HttpUrl, conint, constr, validator

LATEST_VERSION = "latest"
NAMESPACE_SOLVER_KEY = UUID("ca7bdfc4-08e8-11eb-935a-ac9e17b76a71")

# Human-readable unique identifier
KeyIdentifier = constr(strip_whitespace=True, min_length=3)
SolverImageName = constr(regex=COMPUTATIONAL_SERVICE_KEY_RE, strip_whitespace=True)


@functools.lru_cache()
def _compose_solver_id(name, version) -> UUID:
    return uuid3(NAMESPACE_SOLVER_KEY, f"{name}:{version}")


# SOLVER ----------
#
# TODO: this might be in common with Director-v2 models
#
#


class Solver(BaseModel):
    """ A released solver with a specific version """

    # Unique machine identifiers
    name: str = Field(
        ...,
        description="Unique solver name with path namespaces",
        regex=COMPUTATIONAL_SERVICE_KEY_RE,
    )
    version: str = Field(
        ...,
        description="semantic version number of the node",
        regex=VERSION_RE,
        example=["1.0.0", "0.0.1"],
    )
    id: UUID

    # Human readables Identifiers
    title: str = Field(..., description="Human readable name")
    description: Optional[str]
    maintainer: str
    # TODO: consider released: Optional[datetime]  # TODO: turn into required
    # TODO: consider version_aliases: List[str] = []  # remaining tags

    # Links to other resources
    url: Optional[HttpUrl] = Field(..., description="Link to get this resource")

    class Config:
        schema_extra = {
            "example": {
                "name": "simcore/services/comp/isolve",
                "version": "2.1.1",
                "id": "42838344-03de-4ce2-8d93-589a5dcdfd05",
                "title": "iSolve",
                "description": "EM solver",
                "maintainer": "info@itis.swiss",
                "url": "",
            }
        }

    @validator("id", pre=True)
    @classmethod
    def compose_id_with_name_and_version(
        cls, v, values
    ):  # pylint: disable=unused-argument
        if v is None:
            return _compose_solver_id(values["name"], values["version"])
        return v

    @classmethod
    def create_from_image(cls, image_meta: ServiceDockerData) -> "Solver":
        data = image_meta.dict(
            include={"name", "key", "version", "description", "contact"},
        )

        return cls(
            name=data.pop("key"),
            version=data.pop("version"),
            title=data.pop("name"),
            maintainer=data.pop("contact"),
            url=None,
            id=None,
            **data,
        )


# JOBS ----------
#
# TODO: this might be in common with Director-v2 models
#
#
class Job(BaseModel):
    id: UUID = Field(..., description="Job identifier")
    inputs_sha: str
    solver_id: UUID = Field(..., description="Solver running this job")

    #
    # HATEOAS  (Hypermedia as the Engine of Application State)  to GET parent/children resources
    #
    # SEE https://restfulapi.net/hateoas/
    #
    solver_url: HttpUrl = Field(..., description="Link to job parent's solver")
    outputs_url: HttpUrl = Field(..., description="Link to job's outputs")


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


# INPUTS/OUTPUTS ----------
#
#
#


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
                "type": "number",
                "title": "Temperature",
                "value": "33",
            }
        }


class JobOutput(SolverPort):
    value: Union[float, str, int, HttpUrl, None] = Field(
        ..., description="Result value in this output"
    )

    job_id: UUID = Field(..., description="Job that produced this output")

    class Config:
        schema_extra = {
            "example": {
                "name": "SAR",
                "type": "data:application/hdf5",
                "title": "SAR field output file-id",
                "value": "1dc2b1e6-a139-47ad-9e0c-b7b791cd4d7a",
                "job_id": "99d9ac65-9f10-4e2f-a433-b5e412bb037b",
            }
        }
