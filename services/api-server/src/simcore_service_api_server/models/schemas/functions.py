# pylint: disable=protected-access

from enum import StrEnum
from typing import Annotated, Final

from models_library.functions import FunctionID, FunctionJobCollectionID, FunctionJobID
from pydantic import BaseModel, ConfigDict, Field
from servicelib.celery.models import TaskState

_JOB_TASK_RUN_STATUS_PREFIX: Final[str] = "JOB_TASK_RUN_STATUS_"


class FunctionJobsListFilters(BaseModel):
    """Filters for listing function jobs"""

    function_id: Annotated[
        FunctionID | None,
        Field(
            description="Filter by function ID pattern",
        ),
    ] = None

    function_job_ids: Annotated[
        list[FunctionJobID] | None,
        Field(
            description="Filter by function job IDs",
        ),
    ] = None

    function_job_collection_id: Annotated[
        FunctionJobCollectionID | None,
        Field(
            description="Filter by function job collection ID",
        ),
    ] = None

    model_config = ConfigDict(
        extra="ignore",
    )


class FunctionJobCreationTaskStatus(StrEnum):
    PENDING = f"{_JOB_TASK_RUN_STATUS_PREFIX}PENDING"
    STARTED = f"{_JOB_TASK_RUN_STATUS_PREFIX}STARTED"
    RETRY = f"{_JOB_TASK_RUN_STATUS_PREFIX}RETRY"
    SUCCESS = f"{_JOB_TASK_RUN_STATUS_PREFIX}SUCCESS"
    FAILURE = f"{_JOB_TASK_RUN_STATUS_PREFIX}FAILURE"
    NOT_YET_SCHEDULED = "JOB_TASK_NOT_YET_SCHEDULED"  # api-server custom status
    ERROR = "JOB_TASK_CREATION_FAILURE"  # api-server custom status


assert {elm._name_ for elm in TaskState}.union({"NOT_YET_SCHEDULED", "ERROR"}) == {
    elm._name_ for elm in FunctionJobCreationTaskStatus
}
