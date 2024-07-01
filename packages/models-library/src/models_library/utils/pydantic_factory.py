from copy import deepcopy
from typing import Any

from pydantic import BaseModel, create_model


def create_model_with_recursive_config(
    reference_cls: type[BaseModel],
    config_overrides: dict[str, Any],
    new_cls_name_suffix: str = "New",
) -> type[BaseModel]:
    """Creates new model identical to reference_cls and overrides
    recursively all Config with config_overrides.
    """

    class NewConfig(reference_cls.Config):
        pass

    for key, value in config_overrides.items():
        setattr(NewConfig, key, value)

    def _resolve_type(outer_type):
        if hasattr(outer_type, "__origin__"):
            # e.g. dict[str, SomeModel] | None -> dict[str, SomeModelNew] | None
            origin = outer_type.__origin__
            args = outer_type.__args__
            wrapped_args = tuple(_resolve_type(arg) for arg in args)
            return origin[wrapped_args]

        if isinstance(outer_type, type) and issubclass(outer_type, BaseModel):
            return create_model_with_recursive_config(
                outer_type,
                config_overrides,
                new_cls_name_suffix=new_cls_name_suffix,
            )
        return outer_type

    new_fields = {}
    for field_name, model_field in reference_cls.__fields__.items():
        field_type = _resolve_type(model_field.outer_type_)
        new_fields[field_name] = (
            field_type,
            deepcopy(model_field.field_info),
        )

    # Create a new model dynamically
    return create_model(
        f"{reference_cls.__name__}{new_cls_name_suffix}",
        **new_fields,
        __config__=NewConfig,
    )
