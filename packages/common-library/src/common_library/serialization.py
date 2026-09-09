import contextlib
from datetime import timedelta
from typing import Any

from pydantic import AnyUrl, BaseModel, SecretStr, TypeAdapter, ValidationError
from pydantic_core import Url

from .json_serialization import json_dumps, json_loads


def model_dump_with_secrets(
    settings_obj: BaseModel, *, show_secrets: bool, **pydantic_export_options
) -> dict[str, Any]:
    # NOTE: `model_dump(mode="json")` masks `SecretStr` (and coerces other types) *before*
    # the `isinstance` checks below can run, which would keep secrets masked even when
    # `show_secrets=True`. We therefore always dump in python mode and, if the caller
    # requested `mode="json"`, convert the result to a JSON-safe structure at the end.
    export_options = {k: v for k, v in pydantic_export_options.items() if k != "mode"}
    dump_as_json = pydantic_export_options.get("mode") == "json"

    data = settings_obj.model_dump(**export_options)

    settings_cls = settings_obj.__class__

    for field_name in settings_cls.model_fields:
        if field_name not in data:
            continue

        field_data = data[field_name]

        if isinstance(field_data, timedelta):
            data[field_name] = field_data.total_seconds()

        elif isinstance(field_data, SecretStr):
            data[field_name] = field_data.get_secret_value() if show_secrets else f"{field_data}"

        elif isinstance(field_data, (AnyUrl, Url)):
            data[field_name] = f"{field_data}"

        elif isinstance(field_data, dict):
            possible_pydantic_model = settings_obj.__class__.model_fields[field_name].annotation
            # NOTE: data could be a dict which does not represent a pydantic model or a union of models
            with contextlib.suppress(AttributeError, ValidationError):
                data[field_name] = model_dump_with_secrets(
                    TypeAdapter(possible_pydantic_model).validate_python(field_data),
                    show_secrets=show_secrets,
                    **export_options,
                )

    if dump_as_json:
        # ensure a JSON-safe structure (e.g. UUID, datetime, Enum, non-str dict keys)
        data = json_loads(json_dumps(data))

    return data
