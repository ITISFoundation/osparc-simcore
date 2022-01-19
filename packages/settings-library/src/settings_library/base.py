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
from functools import cached_property
from typing import Callable, Tuple, Type

from pydantic import BaseSettings, Extra, SecretStr, ValidationError, validator
from pydantic.error_wrappers import ErrorWrapper
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

    @validator("*", pre=True)
    @classmethod
    def parse_none(cls, v, field: ModelField):
        # WARNING: In nullable fields, envs equal to null or none are parsed as None !!
        if field.allow_none:
            if isinstance(v, str) and v.lower() in ("null", "none"):
                return None
        return v

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
        *,
        on_failure_set_as_required: bool = False,
    ):
        field = cls.__fields__[field_name]

        try:
            # can build default?
            default_value = default_factory()

            # reset default to value
            field.default = default_value
            field.field_info.default = default_value
            field.required = False

        except ValidationError:
            if field.allow_none:
                # reset default to None
                field.default = None
                field.field_info.default = None
                field.required = False
            elif on_failure_set_as_required:
                # reset default to ...
                field.default = None
                field.field_info.default = Ellipsis
                field.required = True
            else:
                raise

    @classmethod
    def create_from_envs(cls):
        """Method to construct settings from env vars

        Sub-settings fields (i.e. fields subclasses of BaseCustomSettings) can set factory
        to create the default from env vars (denoted auto-default factory)

        The auto-default factory sets up a default value that matches the specified type
        or raises AutoDefaultFactoryError

        Notice that if nullable,i.e. Option[SettingsType], the default might resolve in either
        an instance of SettingsType or None.

        SEE https://pydantic-docs.helpmanual.io/usage/settings/#parsing-environment-variable-values
        """
        name: str
        field: ModelField
        auto_default_errors = []

        for name, field in cls.__fields__.items():

            if issubclass(field.type_, BaseCustomSettings):
                subsettings_cls = field.type_

                if field.field_info.default == AUTO_DEFAULT_FROM_ENV_VARS:
                    try:
                        cls._create_default_field(
                            field.name, default_factory=subsettings_cls.create_from_envs
                        )
                    except ValidationError as err:
                        assert err.model
                        auto_default_errors.extend(
                            [
                                ErrorWrapper(e.exc, (field.name,) + e.loc_tuple())
                                for e in err.raw_errors
                            ]
                        )

            elif issubclass(field.type_, BaseSettings):
                raise ValueError(
                    f"{cls}.{name} of type {field.type_} must inherit from BaseCustomSettings"
                )

            elif field.field_info.default == AUTO_DEFAULT_FROM_ENV_VARS:
                raise ValueError(
                    "default=AUTO_DEFAULT_FROM_ENV_VARS can only be used in BaseCustomSettings subclasses"
                    f"but field {cls}.{name} is {field.type_} "
                )

        if auto_default_errors:
            raise AutoDefaultFactoryError(errors=auto_default_errors, model=cls)

        obj = cls()
        return obj
