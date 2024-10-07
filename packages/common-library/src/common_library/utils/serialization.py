from typing import Any

from common_library.utils.pydantic_fields_extension import get_type
from pydantic import BaseModel, SecretStr


def model_dump_with_secrets(
    settings_obj: BaseModel, show_secrets: bool, **pydantic_export_options
) -> dict[str, Any]:
    data = settings_obj.model_dump(**pydantic_export_options)

    for field_name in settings_obj.model_fields:
        if field_name not in data:
            continue

        field_data = data[field_name]

        if isinstance(field_data, SecretStr):
            if show_secrets:
                data[field_name] = field_data.get_secret_value()
            else:
                data[field_name] = str(field_data)
        elif isinstance(field_data, dict):
            field_type = get_type(settings_obj.model_fields[field_name])
            if issubclass(field_type, BaseModel):
                data[field_name] = model_dump_with_secrets(
                    field_type.model_validate(field_data),
                    show_secrets,
                    **pydantic_export_options,
                )

    return data
