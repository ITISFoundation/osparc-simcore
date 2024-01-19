import logging
from collections.abc import Sequence
from functools import cached_property
from typing import Final, get_args

from pydantic import BaseConfig, BaseSettings, Extra, ValidationError, validator
from pydantic.error_wrappers import ErrorList, ErrorWrapper
from pydantic.fields import ModelField, Undefined

logger = logging.getLogger(__name__)

_DEFAULTS_TO_NONE_MSG: Final[
    str
] = "%s auto_default_from_env unresolved, defaulting to None"


class DefaultFromEnvFactoryError(ValidationError):
    ...


def create_settings_from_env(field: ModelField):
    # NOTE: Cannot pass only field.type_ because @prepare_field (when this function is called)
    #  this value is still not resolved (field.type_ at that moment has a weak_ref).
    #  Therefore we keep the entire 'field' but MUST be treated here as read-only

    def _default_factory():
        """Creates default from sub-settings or None (if nullable)"""
        field_settings_cls = field.type_
        try:
            return field_settings_cls()

        except ValidationError as err:
            if field.allow_none:
                # e.g. Optional[PostgresSettings] would warn if defaults to None
                logger.warning(
                    _DEFAULTS_TO_NONE_MSG,
                    field.name,
                )
                return None

            def _prepend_field_name(ee: ErrorList):
                if isinstance(ee, ErrorWrapper):
                    return ErrorWrapper(ee.exc, (field.name, *ee.loc_tuple()))
                assert isinstance(ee, Sequence)  # nosec
                return [_prepend_field_name(e) for e in ee]

            raise DefaultFromEnvFactoryError(
                errors=_prepend_field_name(err.raw_errors),
                model=err.model,
                # FIXME: model = shall be the parent settings?? but I dont find how retrieve it from the field
            ) from err

    return _default_factory


class BaseCustomSettings(BaseSettings):
    """
    - Customized configuration for all settings
    - If a field is a BaseCustomSettings subclass, it allows creating a default from env vars setting the Field
      option 'auto_default_from_env=True'.

    SEE tests for details.
    """

    @validator("*", pre=True)
    @classmethod
    def parse_none(cls, v, field: ModelField):
        # WARNING: In nullable fields, envs equal to null or none are parsed as None !!
        if field.allow_none and isinstance(v, str) and v.lower() in ("null", "none"):
            return None
        return v

    class Config(BaseConfig):
        case_sensitive = True  # All must be capitalized
        extra = Extra.forbid
        allow_mutation = False
        frozen = True
        validate_all = True
        keep_untouched = (cached_property,)

        @classmethod
        def prepare_field(cls, field: ModelField) -> None:
            super().prepare_field(field)

            auto_default_from_env = field.field_info.extra.get(
                "auto_default_from_env", False
            )

            field_type = field.type_
            if args := get_args(field_type):
                field_type = next(a for a in args if a != type(None))

            if issubclass(field_type, BaseCustomSettings):
                if auto_default_from_env:
                    assert field.field_info.default is Undefined
                    assert field.field_info.default_factory is None

                    # Transform it into something like `Field(default_factory=create_settings_from_env(field))`
                    field.default_factory = create_settings_from_env(field)
                    field.default = None
                    field.required = False  # has a default now

            elif issubclass(field_type, BaseSettings):
                msg = f"{cls}.{field.name} of type {field_type} must inherit from BaseCustomSettings"
                raise ValueError(msg)

            elif auto_default_from_env:
                msg = f"auto_default_from_env=True can only be used in BaseCustomSettings subclassesbut field {cls}.{field.name} is {field_type} "
                raise ValueError(msg)

    @classmethod
    def create_from_envs(cls, **overrides):
        # Kept for legacy. Identical to the constructor.
        # Optional to use to make the code more readable
        # More explicit and pylance seems to get less confused
        return cls(**overrides)
