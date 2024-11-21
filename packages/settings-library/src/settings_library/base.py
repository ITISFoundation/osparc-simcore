import logging
from functools import cached_property
from typing import Any, Final, get_origin

from common_library.pydantic_fields_extension import get_type, is_literal, is_nullable
from pydantic import ValidationInfo, field_validator
from pydantic.fields import FieldInfo
from pydantic_core import ValidationError
from pydantic_settings import (
    BaseSettings,
    EnvSettingsSource,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

_logger = logging.getLogger(__name__)

_AUTO_DEFAULT_FACTORY_RESOLVES_TO_NONE_FSTRING: Final[
    str
] = "{field_name} auto_default_from_env unresolved, defaulting to None"


class DefaultFromEnvFactoryError(ValueError):
    def __init__(self, errors):
        super().__init__("Default could not be constructed")
        self.errors = errors


def _create_settings_from_env(field_name: str, info: FieldInfo):
    # NOTE: Cannot pass only field.type_ because @prepare_field (when this function is called)
    #  this value is still not resolved (field.type_ at that moment has a weak_ref).
    #  Therefore we keep the entire 'field' but MUST be treated here as read-only

    def _default_factory():
        """Creates default from sub-settings or None (if nullable)"""
        field_settings_cls = get_type(info)
        try:
            return field_settings_cls()

        except ValidationError as err:
            if is_nullable(info):
                # e.g. Optional[PostgresSettings] would warn if defaults to None
                msg = _AUTO_DEFAULT_FACTORY_RESOLVES_TO_NONE_FSTRING.format(
                    field_name=field_name
                )
                _logger.warning(msg)
                return None
            _logger.warning("Validation errors=%s", err.errors())
            raise DefaultFromEnvFactoryError(errors=err.errors()) from err

    return _default_factory


def _is_auto_default_from_env_enabled(field: FieldInfo) -> bool:
    return bool(
        field.json_schema_extra is not None
        and field.json_schema_extra.get("auto_default_from_env", False)  # type: ignore[union-attr]
    )


_MARKED_AS_UNSET: Final[dict] = {}


class EnvSettingsWithAutoDefaultSource(EnvSettingsSource):
    def __init__(
        self, settings_cls: type[BaseSettings], env_settings: EnvSettingsSource
    ):
        super().__init__(
            settings_cls,
            env_settings.case_sensitive,
            env_settings.env_prefix,
            env_settings.env_nested_delimiter,
            env_settings.env_ignore_empty,
            env_settings.env_parse_none_str,
            env_settings.env_parse_enums,
        )

    def prepare_field_value(
        self,
        field_name: str,
        field: FieldInfo,
        value: Any,
        value_is_complex: bool,  # noqa: FBT001
    ) -> Any:
        prepared_value = super().prepare_field_value(
            field_name, field, value, value_is_complex
        )
        if (
            _is_auto_default_from_env_enabled(field)
            and field.default_factory
            and field.default is None
            and prepared_value == _MARKED_AS_UNSET
        ):
            prepared_value = field.default_factory()
        return prepared_value


class BaseCustomSettings(BaseSettings):
    """
    - Customized configuration for all settings
    - If a field is a BaseCustomSettings subclass, it allows creating a default from env vars setting the Field
      option 'auto_default_from_env=True'.

    SEE tests for details.
    """

    @field_validator("*", mode="before")
    @classmethod
    def _parse_none(cls, v, info: ValidationInfo):
        # WARNING: In nullable fields, envs equal to null or none are parsed as None !!
        if (
            info.field_name
            and is_nullable(cls.model_fields[info.field_name])
            and isinstance(v, str)
            and v.lower() in ("none",)
        ):
            return None
        return v

    model_config = SettingsConfigDict(
        case_sensitive=True,  # All must be capitalized
        extra="forbid",
        frozen=True,
        validate_default=True,
        ignored_types=(cached_property,),
        env_parse_none_str="null",
    )

    @classmethod
    def __pydantic_init_subclass__(cls, **kwargs: Any):
        super().__pydantic_init_subclass__(**kwargs)

        for name, field in cls.model_fields.items():
            auto_default_from_env = _is_auto_default_from_env_enabled(field)
            field_type = get_type(field)

            # Avoids issubclass raising TypeError. SEE test_issubclass_type_error_with_pydantic_models
            is_not_composed = (
                get_origin(field_type) is None
            )  # is not composed as dict[str, Any] or Generic[Base]
            is_not_literal = not is_literal(field)

            if (
                is_not_literal
                and is_not_composed
                and issubclass(field_type, BaseCustomSettings)
            ):
                if auto_default_from_env:
                    # Builds a default factory `Field(default_factory=create_settings_from_env(field))`
                    field.default_factory = _create_settings_from_env(name, field)
                    field.default = None

            elif (
                is_not_literal
                and is_not_composed
                and issubclass(field_type, BaseSettings)
            ):
                msg = f"{cls}.{name} of type {field_type} must inherit from BaseCustomSettings"
                raise ValueError(msg)

            elif auto_default_from_env:
                msg = f"auto_default_from_env=True can only be used in BaseCustomSettings subclasses but field {cls}.{name} is {field_type} "
                raise ValueError(msg)

        cls.model_rebuild(force=True)

    @classmethod
    def create_from_envs(cls, **overrides):
        # Kept for legacy. Identical to the constructor.
        # Optional to use to make the code more readable
        # More explicit and pylance seems to get less confused
        return cls(**overrides)

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        assert env_settings  # nosec
        return (
            init_settings,
            EnvSettingsWithAutoDefaultSource(
                settings_cls, env_settings=env_settings  # type:ignore[arg-type]
            ),
            dotenv_settings,
            file_secret_settings,
        )
