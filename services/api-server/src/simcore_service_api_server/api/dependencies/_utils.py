from typing import Any

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
