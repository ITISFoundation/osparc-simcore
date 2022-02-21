import warnings
from contextlib import suppress
from typing import List, Tuple, Type

from pydantic import BaseSettings, Extra, SecretStr, ValidationError

warnings.warn(
    "models_library.settings will be mostly replaced by settings_library in future versions. "
    "SEE https://github.com/ITISFoundation/osparc-simcore/pull/2395 for details",
    DeprecationWarning,
)


class BaseCustomSettings(BaseSettings):
    class Config:
        case_sensitive = False
        extra = Extra.forbid
        allow_mutation = False
        frozen = True
        validate_all = True
        json_encoders = {
            # FIXME: this should be optional via CLI --show-secret!
            SecretStr: lambda v: v.get_secret_value()
        }

    @classmethod
    def set_defaults_with_default_constructors(
        cls, default_fields: List[Tuple[str, Type["BaseCustomSettings"]]]
    ):
        # This funcion can set defaults on fields that are BaseSettings as well
        # It is used in control construction of defaults.
        # Pydantic offers a defaults_factory but it is executed upon creation of the Settings **class**
        # which is too early for our purpose. Instead, we want to create the defaults just
        # before the settings instance is constructed

        assert issubclass(cls, BaseCustomSettings)

        # Builds defaults at this point
        for name, default_cls in default_fields:
            with suppress(ValidationError):
                default = default_cls()
                field_obj = cls.__fields__[name]
                field_obj.default = default
                field_obj.field_info.default = default
                field_obj.required = False

    @classmethod
    def create_from_envs(cls):
        obj = cls()

        # TODO: perform this check on FieldInfo upon class construction
        if any(isinstance(field, BaseSettings) for field in obj.__fields__):
            raise NotImplementedError(
                "Override in subclass and use set_defaults_with_default_constructors to set sub-settings defaults"
            )
        return obj
