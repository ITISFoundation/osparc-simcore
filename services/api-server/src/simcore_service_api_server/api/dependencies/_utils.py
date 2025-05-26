from typing import Any

from common_library.exclude import as_dict_exclude_none
from pydantic.fields import FieldInfo


def get_query_params(field: FieldInfo) -> dict[str, Any]:
    return as_dict_exclude_none(
        description=field.description,
        examples=field.examples or None,
    )
