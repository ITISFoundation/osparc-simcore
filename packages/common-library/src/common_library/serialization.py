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
            if show_secrets:
                data[field_name] = field_data.get_secret_value()
            else:
                data[field_name] = str(field_data)

        elif isinstance(field_data, Url):
            data[field_name] = str(field_data)

        elif isinstance(field_data, dict):
            field_type = settings_obj.model_fields[field_name].annotation
            with contextlib.suppress(AttributeError, ValidationError):
                data[field_name] = model_dump_with_secrets(
                    TypeAdapter(field_type).validate_python(field_data),
                    show_secrets=show_secrets,
                    **pydantic_export_options,
                )

    return data
