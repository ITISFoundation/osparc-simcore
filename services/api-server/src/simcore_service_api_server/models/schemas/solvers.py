import functools
from datetime import datetime
from enum import Enum
from typing import Optional, Union
from uuid import UUID, uuid3

import packaging.version
from models_library.basic_regex import VERSION_RE
from models_library.services import COMPUTATIONAL_SERVICE_KEY_RE, ServiceDockerData
from packaging.version import Version
from pydantic import BaseModel, Field, HttpUrl, conint, constr, validator

LATEST_VERSION = "latest"
NAMESPACE_SOLVER_KEY = UUID("ca7bdfc4-08e8-11eb-935a-ac9e17b76a71")
NAMESPACE_JOB_KEY = UUID("ca7bdfc4-08e8-11eb-935a-ac9e17b76a71")


@functools.lru_cache()
def _compose_solver_id(name, version) -> UUID:
    return uuid3(NAMESPACE_SOLVER_KEY, f"{name}:{version}")


@functools.lru_cache(maxsize=1024)
def _compose_job_id(solver_id: UUID, inputs_sha: str, created_at: str) -> UUID:
    # NOTE: the date is part of the composition so maxsize to 1000 * sys.getsizeof(UUID) = 1000 * 56bytes elements
    return uuid3(NAMESPACE_JOB_KEY, f"{solver_id}:{inputs_sha}:{created_at}")


# SOLVER ----------
#
#
SolverName = constr(
    strip_whitespace=True,
    regex=COMPUTATIONAL_SERVICE_KEY_RE,
)


class Solver(BaseModel):
    """ A released solver with a specific version """

    # Unique machine identifiers
    name: SolverName = Field(
        ...,
        description="Unique solver name with path namespaces",
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

    # Get links to other resources
    url: Optional[HttpUrl] = Field(..., description="Link to get this resource")

    class Config:
        schema_extra = {
            "examples": [
                {
                    "name": "simcore/services/comp/isolve",
                    "version": "2.1.1",
                    "id": "42838344-03de-4ce2-8d93-589a5dcdfd05",
                    "title": "iSolve",
                    "description": "EM solver",
                    "maintainer": "info@itis.swiss",
                    "url": "https://api.osparc.io/v0/solvers/42838344-03de-4ce2-8d93-589a5dcdfd05",
                }
            ]
        }

    @validator("id", pre=True)
    @classmethod
    def compose_id_with_name_and_version(cls, v, values):
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

    @property
    def pep404_version(self) -> Version:
        """ Rich version type that can be used e.g. to compare """
        return packaging.version.parse(self.version)


# JOBS ----------
#
#


class Job(BaseModel):
    solver_id: UUID = Field(..., description="Solver used to run this job")
    inputs_checksum: str = Field(..., description="Input's checksum")
    created_at: datetime = Field(..., description="Job creation timestamp")
    id: UUID

    # Get links to other resources
    url: Optional[HttpUrl] = Field(..., description="Link to get this resource")
    solver_url: Optional[HttpUrl] = Field(..., description="Link to the solver's job")
    outputs_url: Optional[HttpUrl] = Field(..., description="Link to the job outputs")

    class Config:
        schema_extra = {
            "examples": [
                {
                    "solver_id": "32cfd2c5-ad5c-4086-ba5e-6f76a17dcb7a",
                    "inputs_checksum": "12345",
                    "created_at": "2021-01-22T23:59:52.322176",
                    "id": "f5c44f80-af84-3d45-8836-7933f67959a6",
                    "url": "https://api.osparc.io/v0/jobs/f5c44f80-af84-3d45-8836-7933f67959a6",
                    "solver_url": "https://api.osparc.io/v0/solvers/42838344-03de-4ce2-8d93-589a5dcdfd05",
                    "outputs_url": "https://api.osparc.io/v0/jobs/f5c44f80-af84-3d45-8836-7933f67959a6/outputs",
                }
            ]
        }

    @validator("id", pre=True)
    @classmethod
    def compose_id_with_solver_and_input(cls, v, values):
        if v is None:
            return _compose_job_id(
                values["solver_id"], values["inputs_checksum"], values["created_at"]
            )
        return v

    @classmethod
    def create_now(cls, solver_id: UUID, inputs_checksum: str) -> "Job":
        return cls(
            solver_id=solver_id,
            inputs_checksum=inputs_checksum,
            created_at=datetime.utcnow(),
            url=None,
            solver_url=None,
            outputs_url=None,
            id=None,
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
            "examples": [
                {
                    "name": "T",
                    "type": "number",
                    "title": "Temperature",
                    "value": "33",
                }
            ]
        }


class JobOutput(SolverPort):
    value: PortValue

    job_id: UUID = Field(..., description="Job that produced this output")

    class Config:
        schema_extra = {
            "examples": [
                {
                    "name": "SAR",
                    "type": "data:application/hdf5",
                    "title": "SAR field output file-id",
                    "value": "1dc2b1e6-a139-47ad-9e0c-b7b791cd4d7a",
                    "job_id": "99d9ac65-9f10-4e2f-a433-b5e412bb037b",
                }
            ]
        }
