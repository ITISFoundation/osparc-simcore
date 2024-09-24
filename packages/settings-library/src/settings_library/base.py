import logging
from functools import cached_property
from types import UnionType
from typing import Any, Final, Literal, get_args, get_origin

from pydantic import ValidationInfo, field_validator
from pydantic.fields import FieldInfo
from pydantic_core import PydanticUndefined, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

_logger = logging.getLogger(__name__)

_DEFAULTS_TO_NONE_MSG: Final[
    str
] = "%s auto_default_from_env unresolved, defaulting to None"


class DefaultFromEnvFactoryError(ValueError):
    def __init__(self, errors):
        super().__init__()
        self.errors = errors


def allows_none(info: FieldInfo) -> bool:
    origin = get_origin(info.annotation)  # X | None or Optional[X] will return Union
    if origin is UnionType:
        return any(x in get_args(info.annotation) for x in (type(None), Any))
    return False


def get_type(info: FieldInfo) -> Any:
    field_type = info.annotation
    if args := get_args(info.annotation):
        field_type = next(a for a in args if a != type(None))
    return field_type


def is_literal(info: FieldInfo) -> bool:
    origin = get_origin(info.annotation)
    return origin is Literal


def create_settings_from_env(field_name, field):
    # NOTE: Cannot pass only field.type_ because @prepare_field (when this function is called)
    #  this value is still not resolved (field.type_ at that moment has a weak_ref).
    #  Therefore we keep the entire 'field' but MUST be treated here as read-only

    def _default_factory():
        """Creates default from sub-settings or None (if nullable)"""
        field_settings_cls = get_type(field)
        try:
            return field_settings_cls()

        except ValidationError as err:
            if allows_none(field):
                # e.g. Optional[PostgresSettings] would warn if defaults to None
                _logger.warning(
                    _DEFAULTS_TO_NONE_MSG,
                    field_name,
                )
                return None

            raise DefaultFromEnvFactoryError(errors=err.errors()) from err

    return _default_factory


class BaseCustomSettings(BaseSettings):
    """
    - Customized configuration for all settings
    - If a field is a BaseCustomSettings subclass, it allows creating a default from env vars setting the Field
      option 'auto_default_from_env=True'.

    SEE tests for details.
    """

    @field_validator("*", mode="before")
    @classmethod
    def parse_none(cls, v, info: ValidationInfo):
        # WARNING: In nullable fields, envs equal to null or none are parsed as None !!
        if (
            info.field_name
            and allows_none(cls.model_fields[info.field_name])
            and isinstance(v, str)
            and v.lower() in ("null", "none")
        ):
            return None
        return v

    model_config = SettingsConfigDict(
        case_sensitive=True,  # All must be capitalized
        extra="forbid",
        frozen=True,
        validate_default=False,
        ignored_types=(cached_property,),
        defer_build=True,
    )

    @classmethod
    def __pydantic_init_subclass__(cls, **_kwargs: Any):
        for name, field in cls.model_fields.items():
            auto_default_from_env = (
                field.json_schema_extra is not None
                and field.json_schema_extra.get("auto_default_from_env", False)
            )  # type: ignore[union-attr]
            field_type = get_type(field)

            # Avoids issubclass raising TypeError. SEE test_issubclass_type_error_with_pydantic_models
            is_not_composed = (
                get_origin(field_type) is None
            )  # is not composed as dict[str, Any] or Generic[Base]
            is_not_literal = not get_origin(field.annotation) is Literal

            if (
                is_not_literal
                and is_not_composed
                and issubclass(field_type, BaseCustomSettings)
            ):
                if auto_default_from_env:
                    assert field.default is PydanticUndefined
                    assert field.default_factory is None

                    # Transform it into something like `Field(default_factory=create_settings_from_env(field))`
                    field.default_factory = create_settings_from_env(name, field)
                    field.default = None
                    # field.required = False  # has a default now

            elif (
                is_not_literal
                and is_not_composed
                and issubclass(field_type, BaseSettings)
            ):
                msg = f"{cls}.{name} of type {field_type} must inherit from BaseCustomSettings"
                raise ValueError(msg)

            elif auto_default_from_env:
                msg = f"auto_default_from_env=True can only be used in BaseCustomSettings subclassesbut field {cls}.{name} is {field_type} "
                raise ValueError(msg)

    @classmethod
    def create_from_envs(cls, **overrides):
        # Kept for legacy. Identical to the constructor.
        # Optional to use to make the code more readable
        # More explicit and pylance seems to get less confused
        return cls(**overrides)
