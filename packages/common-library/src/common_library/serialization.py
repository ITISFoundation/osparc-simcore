import contextlib
from datetime import timedelta
from typing import Any

from pydantic import BaseModel, SecretStr, TypeAdapter, ValidationError
from pydantic_core import Url


def model_dump_with_secrets(
    settings_obj: BaseModel, *, show_secrets: bool, **pydantic_export_options
) -> dict[str, Any]:
    data = settings_obj.model_dump(**pydantic_export_options)

    for field_name in settings_obj.model_fields:
        if field_name not in data:
            continue

        field_data = data[field_name]

        if isinstance(field_data, timedelta):
            data[field_name] = field_data.total_seconds()

        elif isinstance(field_data, SecretStr):
            data[field_name] = (
                field_data.get_secret_value() if show_secrets else str(field_data)
            )

        elif isinstance(field_data, Url):
            data[field_name] = str(field_data)

        elif isinstance(field_data, dict):
            possible_pydantic_model = settings_obj.model_fields[field_name].annotation
            # NOTE: data could be a dict which does not represent a pydantic model or a union of models
            with contextlib.suppress(AttributeError, ValidationError):
                data[field_name] = model_dump_with_secrets(
                    TypeAdapter(possible_pydantic_model).validate_python(field_data),
                    show_secrets=show_secrets,
                    **pydantic_export_options,
                )

    return data
