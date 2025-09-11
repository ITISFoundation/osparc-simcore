from typing import Annotated

from models_library.functions import FunctionID, FunctionJobCollectionID, FunctionJobID
from pydantic import BaseModel, ConfigDict, Field


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
