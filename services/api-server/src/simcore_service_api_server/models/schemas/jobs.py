from datetime import datetime
from enum import Enum
from typing import Optional, Union
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, HttpUrl, conint, constr, validator

from ..api_resources import RelativeResourceName

# JOBS ----------
#  - A job can be create on a specific solver or other type of future runner (e.g. a pipeline)
#  - For that reason it also uses global UUIDs as resource identifier
#
#   A job.name from a solver
#    "solvers/isolve/releases/1.3.4/jobs/f622946d-fd29-35b9-a193-abdd1095167c"
#
#   A job.name from a pipeline
#     "pipelines/mySuperDupper/versions/4/jobs/c2789bd2-7385-4e00-91d3-2f100df41185"
#
#   But then both could be also retrieved as a global job resource (perhaps)
#     "jobs/f622946d-fd29-35b9-a193-abdd1095167c"
#     "jobs/c2789bd2-7385-4e00-91d3-2f100df41185"
#


class Job(BaseModel):
    id: UUID
    name: RelativeResourceName

    inputs_checksum: str = Field(..., description="Input's checksum")
    created_at: datetime = Field(..., description="Job creation timestamp")

    # parent
    runner_name: RelativeResourceName = Field(
        ..., description="Runner that executes job"
    )

    # Get links to other resources
    url: Optional[HttpUrl] = Field(..., description="Link to get this resource (self)")
    runner_url: Optional[HttpUrl] = Field(
        ..., description="Link to the solver's job (parent collection)"
    )
    outputs_url: Optional[HttpUrl] = Field(
        ..., description="Link to the job outputs (sub-collection"
    )

    class Config:
        schema_extra = {
            "example": {
                "id": "f622946d-fd29-35b9-a193-abdd1095167c",
                "name": "solvers/isolve/releases/1.3.4/jobs/f622946d-fd29-35b9-a193-abdd1095167c",
                "runner_name": "solvers/isolve/releases/1.3.4",
                "inputs_checksum": "12345",
                "created_at": "2021-01-22T23:59:52.322176",
                "url": "https://api.osparc.io/v0/jobs/f622946d-fd29-35b9-a193-abdd1095167c",
                "runner_url": "https://api.osparc.io/v0/solvers/isolve/releases/1.3.4",
                "outputs_url": "https://api.osparc.io/v0/jobs/f622946d-fd29-35b9-a193-abdd1095167c/outputs",
            }
        }

    @validator("name", pre=True)
    @classmethod
    def check_name(cls, v, values):
        _id = str(values["id"])
        if not v.endswith(f"/{_id}"):
            raise ValueError(f"Resource name [{v}] and id [{_id}] do not match")
        return v

    @classmethod
    def create_now(cls, parent: RelativeResourceName, inputs_checksum: str) -> "Job":
        _id = uuid4()

        return cls(
            name=f"{parent}/{str(_id)}",
            id=_id,
            runner_name=parent,
            inputs_checksum=inputs_checksum,
            created_at=datetime.utcnow(),
            url=None,
            runner_url=None,
            outputs_url=None,
        )


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


class PortValue(BaseModel):
    __root__: Union[float, str, int, HttpUrl, None]


class SolverPort(BaseModel):
    name: str = Field(
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
    value: Optional[PortValue] = None

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
    value: PortValue

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
