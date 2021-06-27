from contextlib import suppress
from functools import cached_property
from typing import List, Tuple, Type

from pydantic import BaseSettings, Extra, SecretStr, ValidationError


class BaseCustomSettings(BaseSettings):
    class Config:
        # SEE https://pydantic-docs.helpmanual.io/usage/model_config/
        case_sensitive = False
        extra = Extra.forbid
        allow_mutation = False
        frozen = True
        validate_all = True
        json_encoders = {SecretStr: lambda v: v.get_secret_value()}
        keep_untouched = (cached_property,)

    @classmethod
    def set_defaults_with_default_constructors(
        cls, default_fields: List[Tuple[str, Type["BaseCustomSettings"]]]
    ):
        # This function can set defaults on fields that are BaseSettings as well
        # It is used in control construction of defaults.
        # Pydantic offers a defaults_factory but it is executed upon creation of the Settings **class**
        # which is too early for our purpose. Instead, we want to create the defaults just
        # before the settings instance is constructed

        assert issubclass(cls, BaseCustomSettings)  # nosec

        # Builds defaults at this point
        for name, default_cls in default_fields:
            with suppress(ValidationError):
                default = default_cls.create_from_envs()
                field_obj = cls.__fields__[name]
                field_obj.default = default
                field_obj.field_info.default = default
                field_obj.required = False

    @classmethod
    def create_from_envs(cls):
        """Constructs settings instance capturing envs (even for defaults) at this call moment"""

        # captures envs here to build defaults for BaseCustomSettings sub-settings
        default_fields = []
        for name, field in cls.__fields__.items():
            if issubclass(field.type_, BaseCustomSettings):
                default_fields.append((name, field.type_))
            elif issubclass(field.type_, BaseSettings):
                raise ValueError(
                    f"{name} field class {field.type_} must inherit from BaseCustomSettings"
                )
        cls.set_defaults_with_default_constructors(default_fields)

        # builds instance
        obj = cls()
        return obj
