from typing import Annotated, Any

from fastapi import Query
from models_library.functions import FunctionJobCollectionsListFilters
from pydantic.fields import FieldInfo


def _get_query_params(field: FieldInfo) -> dict[str, Any]:
    params = {}

    if field.description:
        params["description"] = field.description
    if field.examples:
        params["example"] = next(
            (example for example in field.examples if "*" in example), field.examples[0]
        )
    return params


def get_function_job_collections_filters(
    # pylint: disable=unsubscriptable-object
    has_function_id: Annotated[
        str | None,
        Query(
            **_get_query_params(
                FunctionJobCollectionsListFilters.model_fields["has_function_id"]
            )
        ),
    ] = None,
) -> FunctionJobCollectionsListFilters:
    return FunctionJobCollectionsListFilters(
        has_function_id=has_function_id,
    )
