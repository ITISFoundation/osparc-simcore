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

    new_fields = {}
    for field_name, model_field in reference_cls.__fields__.items():
        if isinstance(model_field.type_, type) and issubclass(
            model_field.type_, BaseModel
        ):
            new_field_type = create_model_with_recursive_config(
                model_field.type_,
                config_overrides,
                new_cls_name_suffix=new_cls_name_suffix,
            )
            new_fields[field_name] = (
                new_field_type,
                deepcopy(model_field.field_info),
            )
        else:
            new_fields[field_name] = (
                model_field.type_,
                deepcopy(model_field.field_info),
            )

    # Create a new model dynamically
    return create_model(
        f"{reference_cls.__name__}{new_cls_name_suffix}",
        **new_fields,
        __config__=NewConfig,
    )
