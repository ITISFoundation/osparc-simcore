import datetime
import hashlib
import logging
from typing import Annotated, TypeAlias
from uuid import UUID, uuid4

from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.projects_state import RunningState
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    PositiveInt,
    StrictBool,
    StrictFloat,
    StrictInt,
    TypeAdapter,
    ValidationError,
    ValidationInfo,
    field_validator,
)
from servicelib.logging_utils import LogLevelInt, LogMessageStr
from starlette.datastructures import Headers

from ...models.schemas.files import File
from ...models.schemas.solvers import Solver
from ..api_resources import (
    RelativeResourceName,
    compose_resource_name,
    split_resource_name,
)

JobID: TypeAlias = UUID

# ArgumentTypes are types used in the job inputs (see ResultsTypes)
ArgumentTypes: TypeAlias = (
    File | StrictFloat | StrictInt | StrictBool | str | list | None
)
KeywordArguments: TypeAlias = dict[str, ArgumentTypes]
PositionalArguments: TypeAlias = list[ArgumentTypes]


def _compute_keyword_arguments_checksum(kwargs: KeywordArguments):
    _dump_str = ""
    for key in sorted(kwargs.keys()):
        value = kwargs[key]
        if isinstance(value, File):
            value = _compute_keyword_arguments_checksum(value.model_dump())
        else:
            value = str(value)
        _dump_str += f"{key}:{value}"
    return hashlib.sha256(_dump_str.encode("utf-8")).hexdigest()


# JOB SUB-RESOURCES  ----------
#
#  - Wrappers for input/output values
#  - Input/outputs are defined in service metadata
#  - custom metadata
#


class JobInputs(BaseModel):
    # NOTE: this is different from the resource JobInput (TBD)
    values: KeywordArguments

    # TODO: gibt es platz fuer metadata?

    model_config = ConfigDict(
        frozen=True,
        json_schema_extra={
            "example": {
                "values": {
                    "x": 4.33,
                    "n": 55,
                    "title": "Temperature",
                    "enabled": True,
                    "input_file": {
                        "filename": "input.txt",
                        "id": "0a3b2c56-dbcd-4871-b93b-d454b7883f9f",
                    },
                }
            }
        },
    )

    def compute_checksum(self):
        return _compute_keyword_arguments_checksum(self.values)


class JobOutputs(BaseModel):
    # TODO: JobOutputs is a resources!

    job_id: JobID = Field(..., description="Job that produced this output")

    # TODO: an output could be computed before than the others? has a state? not-ready/ready?
    results: KeywordArguments

    # TODO: an error might have occurred at the level of the job, i.e. affects all outputs, or only
    # on one specific output.

    model_config = ConfigDict(
        frozen=True,
        json_schema_extra={
            "example": {
                "job_id": "99d9ac65-9f10-4e2f-a433-b5e412bb037b",
                "results": {
                    "maxSAR": 4.33,
                    "n": 55,
                    "title": "Specific Absorption Rate",
                    "enabled": False,
                    "output_file": {
                        "filename": "sar_matrix.txt",
                        "id": "0a3b2c56-dbcd-4871-b93b-d454b7883f9f",
                    },
                },
            }
        },
    )

    def compute_results_checksum(self):
        return _compute_keyword_arguments_checksum(self.results)


# Limits metadata values
MetaValueType: TypeAlias = StrictBool | StrictInt | StrictFloat | str


class JobMetadataUpdate(BaseModel):
    metadata: dict[str, MetaValueType] = Field(
        default_factory=dict, description="Custom key-value map"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "metadata": {
                    "bool": "true",
                    "int": "42",
                    "float": "3.14",
                    "str": "hej med dig",
                }
            }
        }
    )


class JobMetadata(BaseModel):
    job_id: JobID = Field(..., description="Parent Job")
    metadata: dict[str, MetaValueType] = Field(..., description="Custom key-value map")

    # Links
    url: HttpUrl | None = Field(..., description="Link to get this resource (self)")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "job_id": "3497e4de-0e69-41fb-b08f-7f3875a1ac4b",
                "metadata": {
                    "bool": "true",
                    "int": "42",
                    "float": "3.14",
                    "str": "hej med dig",
                },
                "url": "https://f02b2452-1dd8-4882-b673-af06373b41b3.fake",
            }
        }
    )


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
    id: JobID  # noqa: A003
    name: RelativeResourceName

    inputs_checksum: str = Field(..., description="Input's checksum")
    created_at: datetime.datetime = Field(..., description="Job creation timestamp")

    # parent
    runner_name: RelativeResourceName = Field(
        ..., description="Runner that executes job"
    )

    # Get links to other resources
    url: HttpUrl | None = Field(..., description="Link to get this resource (self)")
    runner_url: HttpUrl | None = Field(
        ..., description="Link to the solver's job (parent collection)"
    )
    outputs_url: HttpUrl | None = Field(
        ..., description="Link to the job outputs (sub-collection)"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "f622946d-fd29-35b9-a193-abdd1095167c",
                "name": "solvers/isolve/releases/1.3.4/jobs/f622946d-fd29-35b9-a193-abdd1095167c",
                "runner_name": "solvers/isolve/releases/1.3.4",
                "inputs_checksum": "12345",
                "created_at": "2021-01-22T23:59:52.322176",
                "url": "https://api.osparc.io/v0/solvers/isolve/releases/1.3.4/jobs/f622946d-fd29-35b9-a193-abdd1095167c",
                "runner_url": "https://api.osparc.io/v0/solvers/isolve/releases/1.3.4",
                "outputs_url": "https://api.osparc.io/v0/solvers/isolve/releases/1.3.4/jobs/f622946d-fd29-35b9-a193-abdd1095167c/outputs",
            }
        }
    )

    @field_validator("name", mode="before")
    @classmethod
    def check_name(cls, v, info: ValidationInfo):
        _id = str(info.data["id"])
        if not v.endswith(f"/{_id}"):
            msg = f"Resource name [{v}] and id [{_id}] do not match"
            raise ValueError(msg)
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
            created_at=datetime.datetime.now(tz=datetime.timezone.utc),
            url=None,
            runner_url=None,
            outputs_url=None,
        )

    @classmethod
    def create_solver_job(cls, *, solver: Solver, inputs: JobInputs):
        return Job.create_now(
            parent_name=solver.name,
            inputs_checksum=inputs.compute_checksum(),
        )

    @classmethod
    def compose_resource_name(
        cls, parent_name: RelativeResourceName, job_id: UUID
    ) -> RelativeResourceName:
        # CAREFUL, this is not guarantee a UNIQUE identifier since the resource
        # could have some alias entrypoints and the wrong parent_name might be introduced here
        collection_or_resource_ids = [
            *split_resource_name(parent_name),
            "jobs",
            f"{job_id}",
        ]
        return compose_resource_name(*collection_or_resource_ids)

    @property
    def resource_name(self) -> str:
        """Relative Resource Name"""
        return self.name


PercentageInt: TypeAlias = Annotated[int, Field(ge=0, le=100)]


class JobStatus(BaseModel):
    # NOTE: About naming. The result of an inspection on X returns a Status object
    #  What is the status of X? What sort of state is X in?
    #  SEE https://english.stackexchange.com/questions/12958/status-vs-state

    job_id: JobID
    state: RunningState
    progress: PercentageInt = Field(default=0)

    # Timestamps on states
    submitted_at: datetime.datetime = Field(
        ..., description="Last modification timestamp of the solver job"
    )
    started_at: datetime.datetime | None = Field(
        None,
        description="Timestamp that indicate the moment the solver starts execution or None if the event did not occur",
    )
    stopped_at: datetime.datetime | None = Field(
        None,
        description="Timestamp at which the solver finished or killed execution or None if the event did not occur",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "job_id": "145beae4-a3a8-4fde-adbb-4e8257c2c083",
                "state": RunningState.STARTED,
                "progress": 3,
                "submitted_at": "2021-04-01 07:15:54.631007",
                "started_at": "2021-04-01 07:16:43.670610",
                "stopped_at": None,
            }
        }
    )


class JobPricingSpecification(BaseModel):
    pricing_plan: PositiveInt = Field(..., alias="x-pricing-plan")
    pricing_unit: PositiveInt = Field(..., alias="x-pricing-unit")

    model_config = ConfigDict(extra="ignore")

    @classmethod
    def create_from_headers(cls, headers: Headers) -> "JobPricingSpecification | None":
        try:
            return TypeAdapter(cls).validate_python(headers)
        except ValidationError:
            return None


class JobLog(BaseModel):
    job_id: ProjectID
    node_id: NodeID | None = None
    log_level: LogLevelInt
    messages: list[LogMessageStr]

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "job_id": "145beae4-a3a8-4fde-adbb-4e8257c2c083",
                "node_id": "3742215e-6756-48d2-8b73-4d043065309f",
                "log_level": logging.DEBUG,
                "messages": ["PROGRESS: 5/10"],
            }
        }
    )
