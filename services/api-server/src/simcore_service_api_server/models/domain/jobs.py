import datetime
from typing import TypeAlias
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)

from ..api_resources import (
    RelativeResourceName,
)

JobID: TypeAlias = UUID
# JOB SUB-RESOURCES  ----------
#
#  - Wrappers for input/output values
#  - Input/outputs are defined in service metadata
#  - custom metadata
#


class Job(BaseModel):
    id: JobID
    name: RelativeResourceName
    job_parent_resource_name: RelativeResourceName

    created_at: datetime.datetime = Field(..., description="Job creation timestamp")

    # parent
    runner_name: RelativeResourceName = Field(
        ..., description="Runner that executes job"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "f622946d-fd29-35b9-a193-abdd1095167c",
                "name": "solvers/isolve/releases/1.3.4/jobs/f622946d-fd29-35b9-a193-abdd1095167c",
                "runner_name": "solvers/isolve/releases/1.3.4",
                "inputs_checksum": "12345",
                "created_at": "2021-01-22T23:59:52.322176",
            }
        }
    )
