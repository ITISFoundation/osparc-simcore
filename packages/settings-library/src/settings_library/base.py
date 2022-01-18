""" Customizes pydantic's BaseSettings class and extends it to allow embedded BaseSettings (not only BaseModels)


+ MOTIVATION:

    If you create a model that inherits from BaseSettings, the model initialiser will
    attempt to determine the values of any fields not passed as keyword arguments by reading from the environment
    (Default values will still be used if the matching environment variable is not set.)

    osparc's services share many configurations (e.g. access postgress) which are commas pydantic settings as
    well (e.g. settings_library.postgres.PostgresSettings )


SEE https://pydantic-docs.helpmanual.io/usage/settings/:
"""


import logging
import os
from functools import cached_property
from typing import Callable, Tuple, Type

from pydantic import BaseSettings, Extra, SecretStr, ValidationError
from pydantic.fields import ModelField

logger = logging.getLogger(__name__)


class AutoDefaultType:
    ...


AUTO_DEFAULT_FROM_ENV_VARS = AutoDefaultType()

NameSettingsTypePair = Tuple[str, Type["BaseCustomSettings"]]


class AutoDefaultFactoryError(ValidationError):
    ...


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
    def _create_default_field(
        cls,
        field_name,
        default_factory: Callable,
    ):
        field = cls.__fields__[field_name]
        try:
            default_value = default_factory()

            # reset default
            field.default = default_value
            field.field_info.default = default_value
            field.required = False

        except ValidationError as err:
            logger.error(
                (
                    "Could not validate '%s', %s "
                    "contains errors, see below:\n%s"
                    "\n======ENV_VARS=====\n%s"
                    "\n==================="
                ),
                cls.__name__,
                f"{field=}",
                f"{err}",
                "\n".join(f"{k}={v}" for k, v in os.environ.items()),
            )
            raise AutoDefaultFactoryError(
                errors=err.raw_errors, model=err.model
            ) from err

    @classmethod
    def create_from_envs(cls):
        """Extend default constructor of BaseSettings by adding an auto default factory for
            fields that are subclasses of BaseCustomSettings.

            The auto default factory sets up a default value from an envs capture

        SEE https://pydantic-docs.helpmanual.io/usage/settings/#parsing-environment-variable-values
        """
        name: str
        field: ModelField

        for name, field in cls.__fields__.items():

            if issubclass(field.type_, BaseCustomSettings):

                if field.field_info.default == AUTO_DEFAULT_FROM_ENV_VARS:
                    subsettings_cls = field.type_
                    cls._create_default_field(
                        field.name, default_factory=subsettings_cls.create_from_envs
                    )

            elif issubclass(field.type_, BaseSettings):
                raise ValueError(
                    f"{cls}.{name} of type {field.type_} must inherit from BaseCustomSettings"
                )

            elif field.field_info.default == AUTO_DEFAULT_FROM_ENV_VARS:
                raise ValueError(
                    "default=AUTO_DEFAULT can only be used in BaseCustomSettings subclasses"
                    f"but field {cls}.{name} is of type {field.type_} "
                )

        obj = cls()
        return obj
