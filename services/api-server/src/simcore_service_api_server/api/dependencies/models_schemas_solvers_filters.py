from typing import Annotated

from fastapi import Query

from ...models.schemas.solvers_filters import SolversListFilters
from ._utils import _get_query_params


def get_solvers_filters(
    # pylint: disable=unsubscriptable-object
    solver_id: Annotated[
        str | None,
        Query(**_get_query_params(SolversListFilters.model_fields["solver_id"])),
    ] = None,
    version_display: Annotated[
        str | None,
        Query(**_get_query_params(SolversListFilters.model_fields["version_display"])),
    ] = None,
) -> SolversListFilters:
    return SolversListFilters(
        solver_id=solver_id,
        version_display=version_display,
    )
