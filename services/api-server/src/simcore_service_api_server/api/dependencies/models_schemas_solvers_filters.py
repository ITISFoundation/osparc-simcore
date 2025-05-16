from typing import Annotated

from fastapi import Query

from ...models.schemas.solvers_filters import SolversListFilters


def get_solvers_filters(
    solver_id: Annotated[
        str | None,
        Query(
            description="Filter by solver ID pattern",
            example="simcore/services/comp/*",
        ),
    ] = None,
    version_display: Annotated[
        str | None,
        Query(
            description="Filter by version display pattern",
            example=["*2023-*"],
        ),
    ] = None,
) -> SolversListFilters:
    """FastAPI dependency to extract solver filters from query parameters"""
    return SolversListFilters(
        solver_id=solver_id,
        version_display=version_display,
    )
