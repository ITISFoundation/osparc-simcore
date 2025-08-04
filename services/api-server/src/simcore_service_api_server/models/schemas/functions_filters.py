from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class FunctionJobsListFilters(BaseModel):
    """Filters for listing function jobs"""

    function_id: Annotated[
        str | None,
        Field(
            description="Filter by function ID pattern",
        ),
    ] = None

    model_config = ConfigDict(
        extra="ignore",
    )
