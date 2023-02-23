import hashlib
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Union
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, HttpUrl, conint, validator

from ...models.config import BaseConfig
from ...models.schemas.files import File
from ...models.schemas.solvers import Solver
from ..api_resources import (
    RelativeResourceName,
    compose_resource_name,
    split_resource_name,
)

# FIXME: all ints and bools will be floats
# TODO: evaluate how coupled is this to InputTypes/OUtputTypes
ArgumentType = Union[File, float, int, bool, str, None]
KeywordArguments = dict[str, ArgumentType]
PositionalArguments = list[ArgumentType]


def compute_checksum(kwargs: KeywordArguments):
    _dump_str = ""
    for key in sorted(kwargs.keys()):
        value = kwargs[key]
        if isinstance(value, File):
            value = compute_checksum(value.dict())
        else:
            value = str(value)
        _dump_str += f"{key}:{value}"
    return hashlib.sha256(_dump_str.encode("utf-8")).hexdigest()


# JOB INPUTS/OUTPUTS ----------
#
#  - Wrappers for input/output values
#  - Input/outputs are defined in service metadata
#


class JobInputs(BaseModel):
    # NOTE: this is different from the resource JobInput (TBD)
    values: KeywordArguments

    # TODO: gibt es platz fuer metadata?

    class Config(BaseConfig):
        frozen = True
        allow_mutation = False
        schema_extra = {
            "example": {
                "values": {
                    "x": 4.33,
                    "n": 55,
                    "title": "Temperature",
                    "enabled": True,
                    "input_file": File(
                        filename="input.txt", id="0a3b2c56-dbcd-4871-b93b-d454b7883f9f"
                    ),
                }
            }
        }

    def compute_checksum(self):
        return compute_checksum(self.values)


class JobOutputs(BaseModel):
    # TODO: JobOutputs is a resources!

    job_id: UUID = Field(..., description="Job that produced this output")

    # TODO: an output could be computed before than the others? has a state? not-ready/ready?
    results: KeywordArguments

    # TODO: an error might have occurred at the level of the job, i.e. affects all outputs, or only
    # on one specific output.
    # errors: list[JobErrors] = []

    class Config(BaseConfig):
        frozen = True
        allow_mutation = False
        schema_extra = {
            "example": {
                "job_id": "99d9ac65-9f10-4e2f-a433-b5e412bb037b",
                "results": {
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

    def compute_results_checksum(self):
        return compute_checksum(self.results)


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

    class Config(BaseConfig):
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

    # constructors ------

    @classmethod
    def create_now(
        cls, parent_name: RelativeResourceName, inputs_checksum: str
    ) -> "Job":
        global_uuid = uuid4()

        return cls(
            name=cls.compose_resource_name(parent_name, global_uuid),
            id=global_uuid,
            runner_name=parent_name,
            inputs_checksum=inputs_checksum,
            created_at=datetime.now(timezone.utc).replace(tzinfo=None),
            url=None,
            runner_url=None,
            outputs_url=None,
        )

    @classmethod
    def create_solver_job(cls, *, solver: Solver, inputs: JobInputs):
        job = Job.create_now(
            parent_name=solver.name, inputs_checksum=inputs.compute_checksum()
        )
        return job

    @classmethod
    def compose_resource_name(
        cls, parent_name: RelativeResourceName, job_id: UUID
    ) -> str:
        # CAREFUL, this is not guarantee a UNIQUE identifier since the resource
        # could have some alias entrypoints and the wrong parent_name might be introduced here
        collection_or_resource_ids = split_resource_name(parent_name) + ["jobs", job_id]
        return compose_resource_name(*collection_or_resource_ids)

    @property
    def resource_name(self) -> str:
        """Relative Resource Name"""
        return self.name


# TODO: these need to be in sync with computational task states
class TaskStates(str, Enum):
    UNKNOWN = "UNKNOWN"
    PUBLISHED = "PUBLISHED"
    NOT_STARTED = "NOT_STARTED"
    PENDING = "PENDING"
    STARTED = "STARTED"
    RETRY = "RETRY"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    ABORTED = "ABORTED"


PercentageInt: type[int] = conint(ge=0, le=100)


class JobStatus(BaseModel):
    # NOTE: About naming. The result of an inspection on X returns a Status object
    #  What is the status of X? What sort of state is X in?
    #  SEE https://english.stackexchange.com/questions/12958/status-vs-state

    job_id: UUID
    state: TaskStates
    progress: PercentageInt = 0

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

    class Config(BaseConfig):
        # frozen = True
        # allow_mutation = False
        schema_extra = {
            "example": {
                "job_id": "145beae4-a3a8-4fde-adbb-4e8257c2c083",
                "state": TaskStates.STARTED,
                "progress": 3,
                "submitted_at": "2021-04-01 07:15:54.631007",
                "started_at": "2021-04-01 07:16:43.670610",
                "stopped_at": None,
            }
        }

    def take_snapshot(self, event: str = "submitted"):
        setattr(self, f"{event}_at", datetime.now(timezone.utc).replace(tzinfo=None))
        return getattr(self, f"{event}_at")
