from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Union
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, HttpUrl, conint, validator

from ...models.schemas.files import File
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
    # NOTE: About naming. The result of an inspection on X returns a Status object
    #  What is the status of X? What sort of state is X in?
    #  SEE https://english.stackexchange.com/questions/12958/status-vs-state

    job_id: UUID
    state: TaskStates
    progress: conint(ge=0, le=100) = 0

    # Timestamps on states
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

    def snapshot(self, event: str = "submitted"):
        setattr(self, f"{event}_at", datetime.utcnow())
        return getattr(self, f"{event}_at")


# INPUTS/OUTPUTS ----------
#


# FIXME: all ints and bools will be floats

ArgumentType = Union[File, float, int, bool, str, None]
KeywordArguments = Dict[str, ArgumentType]
PositionalArguments = List[ArgumentType]


class Inputs(BaseModel):
    # NOTE: this is different from the resource JobInput (TBD)
    __root__: KeywordArguments

    class Config:
        schema_extra = {
            "example": {
                "x": 4.33,
                "n": 55,
                "title": "Temperature",
                "enabled": True,
                "input_file": File(
                    filename="input.txt", id="0a3b2c56-dbcd-4871-b93b-d454b7883f9f"
                ),
            }
        }


class JobResults(BaseModel):
    job_id: UUID = Field(..., description="Job that produced this output")
    outputs: KeywordArguments

    class Config:
        schema_extra = {
            "example": {
                "job_id": "99d9ac65-9f10-4e2f-a433-b5e412bb037b",
                "outputs": {
                    "maxSAR": 4.33,
                    "n": 55,
                    "title": "Specific Absorption Rate",
                    "enabled": False,
                    "output_file": File(
                        filename="sar_matrix.txt",
                        id="0a3b2c56-dbcd-4871-b93b-d454b7883f9f",
                    ),
                },
            }
        }
