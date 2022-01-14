import logging
import os
from functools import cached_property
from typing import List, Tuple, Type

from pydantic import BaseSettings, Extra, SecretStr, ValidationError

logger = logging.getLogger(__name__)


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
    def _set_defaults_with_default_constructors(
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
        """Constructs settings instance capturing envs (even for defaults) at this call moment"""

        # captures envs here to build defaults for BaseCustomSettings sub-settings
        default_fields = []
        for name, field in cls.__fields__.items():
            if issubclass(field.type_, BaseCustomSettings):
                # NOTE: all non-Optional BaseCustomSettings fields that are required, get
                # automatically a default.
                # FIXME: still does not detect non-compact capture if Optional[PostgresSettings]
                if field.required and not field.default:
                    default_fields.append((name, field.type_))
            elif issubclass(field.type_, BaseSettings):
                raise ValueError(
                    f"{name} field class models {field.type_} must inherit from BaseCustomSettings"
                )
        cls._set_defaults_with_default_constructors(default_fields)

        # builds instance
        obj = cls()
        return obj
