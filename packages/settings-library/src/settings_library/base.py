""" Customizes pydantic's BaseSettings class and extends it to allow embedded BaseSettings (not only BaseModels)




SEE https://pydantic-docs.helpmanual.io/usage/settings/:
    If you create a model that inherits from BaseSettings, the model initialiser will
    attempt to determine the values of any fields not passed as keyword arguments by reading from the environment
    (Default values will still be used if the matching environment variable is not set.)



"""


import logging
import os
from functools import cached_property
from typing import List, Tuple, Type

from pydantic import BaseSettings, Extra, SecretStr, ValidationError
from pydantic.fields import ModelField

logger = logging.getLogger(__name__)


class AutoDefaultType:
    ...


AUTO_DEFAULT_FROM_ENV_VARS = AutoDefaultType()

NameSettingsTypePair = Tuple[str, Type["BaseCustomSettings"]]


class BaseCustomSettings(BaseSettings):
    """
    - Allows nested 'BaseCustomSettings' (i.e. fields that captures)

    """

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
    def _reset_field_defaults(cls, default_fields: List[NameSettingsTypePair]):
        # This function can set defaults on fields that are BaseSettings as well
        # It is used in control construction of defaults.
        # Pydantic offers a defaults_factory but it is executed upon creation of the Settings **class**
        # which is too early for our purpose. Instead, we want to create the defaults just
        # before the settings instance is constructed

        assert issubclass(cls, BaseCustomSettings)  # nosec

        # Builds defaults at this point
        for name, default_cls in default_fields:
            try:
                default = default_cls.create_from_envs()
                field_obj = cls.__fields__[name]
                field_obj.default = default
                field_obj.field_info.default = default
                field_obj.required = False
            except ValidationError as e:
                logger.error(
                    (
                        "Could not validate '%s', field '%s' "
                        "contains errors, see below:\n%s"
                        "\n======ENV_VARS=====\n%s"
                        "\n==================="
                    ),
                    cls.__name__,
                    default_cls.__name__,
                    str(e),
                    "\n".join(f"{k}={v}" for k, v in os.environ.items()),
                )
                raise e

    @classmethod
    def create_from_envs(cls):
        """Constructs settings instance capturing envs (even for defaults) at this call moment


        -

        SEE https://pydantic-docs.helpmanual.io/usage/settings/#parsing-environment-variable-values

        """

        # captures envs here to build defaults for BaseCustomSettings sub-settings
        name: str
        field: ModelField
        defaults_to_create: List[NameSettingsTypePair] = []

        for name, field in cls.__fields__.items():
            if field.field_info.default == AUTO_DEFAULT_FROM_ENV_VARS:
                if issubclass(field.type_, BaseCustomSettings):
                    defaults_to_create.append((name, field.type_))
                elif issubclass(field.type_, BaseSettings):
                    raise ValueError(
                        f"{cls}.{name} of type {field.type_} must inherit from BaseCustomSettings"
                    )
                else:
                    raise ValueError(
                        "default=AUTO_DEFAULT can only be used in BaseCustomSettings subclasses"
                        f"but field {cls}.{name} is of type {field.type_} "
                    )
        cls._reset_field_defaults(defaults_to_create)

        # builds instance
        obj = cls()
        return obj
