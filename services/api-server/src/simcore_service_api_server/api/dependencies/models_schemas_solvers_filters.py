from typing import Annotated, Any

from fastapi import Query
from pydantic.fields import FieldInfo

from ...models.schemas.solvers_filters import SolversListFilters


def _get_query_params(field: FieldInfo) -> dict[str, Any]:
    params = {}

    if field.description:
        params["description"] = field.description
    if field.examples:
        params["example"] = next(
            (example for example in field.examples if "*" in example), field.examples[0]
        )
    return params


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
