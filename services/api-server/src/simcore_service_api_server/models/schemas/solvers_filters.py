from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class SolversListFilters(BaseModel):
    """Filters for listing solvers"""

    solver_id: Annotated[
        str | None,
        Field(
            description="Filter by solver ID pattern (e.g. 'simcore/services/comp/itis/*')",
            examples=["simcore/services/comp/itis/sleeper", "simcore/services/comp/*"],
        ),
    ] = None

    version_display: Annotated[
        str | None,
        Field(
            description="Filter by version display pattern (e.g. '*2023*')",
            examples=["2.1.1-2023-10-01", "*2023*"],
        ),
    ] = None

    model_config = ConfigDict(
        extra="ignore",
    )
