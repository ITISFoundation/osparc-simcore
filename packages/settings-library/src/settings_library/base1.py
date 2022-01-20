from functools import cached_property
from typing import get_args

from pydantic import BaseConfig, BaseSettings, Extra, ValidationError, validator
from pydantic.error_wrappers import ErrorWrapper
from pydantic.fields import ModelField, Undefined
from pydantic.types import SecretStr


class DefaultFromEnvFactoryError(ValidationError):
    ...


def create_settings_from_env(field):
    # Keeps a reference of field but MUST nothing should be modified there
    # cannot pass only field.type_ because @prepare_field still not resolved!

    def _default_factory():
        """Creates default from sub-settings or None (if nullable)"""
        settings_cls = (
            field.outer_type_
        )  # FIXME: this is wrong, it is NOT the container class
        sub_settings_cls = field.type_
        try:
            return sub_settings_cls()

        except ValidationError as err:
            if field.allow_none:
                return None

            raise DefaultFromEnvFactoryError(
                errors=[
                    ErrorWrapper(e.exc, (field.name,) + e.loc_tuple())
                    for e in err.raw_errors
                ],
                model=settings_cls,
            ) from err

    return _default_factory


class BaseCustomSettings(BaseSettings):
    @validator("*", pre=True)
    @classmethod
    def parse_none(cls, v, field: ModelField):
        # WARNING: In nullable fields, envs equal to null or none are parsed as None !!
        if field.allow_none:
            if isinstance(v, str) and v.lower() in ("null", "none"):
                return None
        return v

    class Config(BaseConfig):
        case_sensitive = False  # All must be capitalized
        extra = Extra.forbid
        allow_mutation = False
        frozen = True
        validate_all = True
        json_encoders = {SecretStr: lambda v: v.get_secret_value()}
        keep_untouched = (cached_property,)

        @classmethod
        def prepare_field(cls, field: ModelField) -> None:
            super().prepare_field(field)

            # print("field:", json.dumps(get_attrs_tree(field), indent=2))

            auto_default_from_env = field.field_info.extra.get(
                "auto_default_from_env", False
            )
            # TODO: if from-env factory fails and is required, we could check if field-name exists in
            # os environ otherwise raise

            field_type = field.type_
            if args := get_args(field_type):
                # TODO: skip all the way if none of these types
                field_type = next(a for a in args if a != type(None))

            if issubclass(field_type, BaseCustomSettings):

                if auto_default_from_env:

                    assert field.field_info.default is Undefined
                    assert field.field_info.default_factory is None

                    field.default_factory = create_settings_from_env(field)

                    # TODO: check if
                    # Undefined required -> required=true
                    # Undefined default and no factor -> default=None
                    field.required = False

            elif issubclass(field_type, BaseSettings):
                raise ValueError(
                    f"{cls}.{field.name} of type {field_type} must inherit from BaseCustomSettings"
                )

            elif auto_default_from_env:
                raise ValueError(
                    "auto_default_from_env=True can only be used in BaseCustomSettings subclasses"
                    f"but field {cls}.{field.name} is {field_type} "
                )
