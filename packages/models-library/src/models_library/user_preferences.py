from collections.abc import Mapping
from enum import auto
from typing import Annotated, Any, ClassVar, Final, Literal, Self

from common_library.json_serialization import json_dumps
from common_library.pydantic_fields_extension import get_type
from pydantic import BaseModel, Field, create_model
from pydantic._internal._model_construction import ModelMetaclass
from pydantic.fields import FieldInfo
from pydantic_core import SchemaError

from .services import ServiceKey, ServiceVersion
from .utils.enums import StrAutoEnum


class _AutoRegisterMeta(ModelMetaclass):
    registered_user_preference_classes: ClassVar[dict[str, type]] = {}

    def __new__(cls, name, bases, attrs, *args, **kwargs):
        new_class = super().__new__(cls, name, bases, attrs, *args, **kwargs)

        if name != cls.__name__:
            if name in cls.registered_user_preference_classes:
                msg = (
                    f"Class named '{name}' was already defined at "
                    f"{cls.registered_user_preference_classes[name]}."
                    " Please choose a different class name!"
                )
                raise TypeError(msg)
            cls.registered_user_preference_classes[name] = new_class

        return new_class


type PreferenceName = str
type PreferenceIdentifier = str


class _ExtendedBaseModel(BaseModel, metaclass=_AutoRegisterMeta): ...


class PreferenceType(StrAutoEnum):
    FRONTEND = auto()
    USER_SERVICE = auto()


class NoPreferenceFoundError(RuntimeError):
    def __init__(self, preference_name) -> None:
        self.preference_name = preference_name
        super().__init__(f"No preference class found for provided {preference_name=}")


_ALLOWED_VALUE_CONSTRAINTS: Final[frozenset[str]] = frozenset(
    {"ge", "gt", "le", "lt", "max_length", "min_length", "multiple_of", "pattern"}
)

_VALUE_VALIDATOR_CLASSES: Final[dict[tuple[type, str], type[BaseModel]]] = {}


class InvalidValueConstraintsError(ValueError):
    def __init__(self, preference_name: PreferenceName, reason: str) -> None:
        self.preference_name = preference_name
        self.reason = reason
        super().__init__(f"Invalid value constraints for {preference_name=}: {reason}")


def _raise_if_not_allowed(preference_name: PreferenceName, constraints: dict[str, Any]) -> None:
    if rejected := set(constraints) - _ALLOWED_VALUE_CONSTRAINTS:
        raise InvalidValueConstraintsError(
            preference_name,
            f"unsupported {sorted(rejected)}, allowed are {sorted(_ALLOWED_VALUE_CONSTRAINTS)}",
        )


class _BaseUserPreferenceModel(_ExtendedBaseModel):
    preference_type: PreferenceType = Field(..., description="distinguish between the types of preferences")

    value: Any = Field(..., description="value of the preference")

    # NOTE: enforced only when setting the value, never by this model itself, so that
    # values allowed by a looser deployment configuration remain readable.
    value_constraints: ClassVar[dict[str, Any]] = {}

    @classmethod
    def __pydantic_init_subclass__(cls, **kwargs: Any) -> None:
        super().__pydantic_init_subclass__(**kwargs)
        _raise_if_not_allowed(cls.get_preference_name(), cls.value_constraints)

    @classmethod
    def get_value_constraints(cls, overrides: dict[str, Any] | None = None) -> dict[str, Any]:
        """Constraints declared by the class, with `overrides` taking precedence per key."""
        if overrides is not None and not isinstance(overrides, Mapping):
            raise InvalidValueConstraintsError(cls.get_preference_name(), f"expected a mapping, got {type(overrides)}")
        constraints = {**cls.value_constraints, **(overrides or {})}
        _raise_if_not_allowed(cls.get_preference_name(), constraints)
        return constraints

    @classmethod
    def build_value_validator(cls, overrides: dict[str, Any] | None = None) -> type[BaseModel]:
        """Model whose only field validates a preference value against `value_constraints` merged with `overrides`."""
        # pylint: disable=unsubscriptable-object
        preference_name = cls.get_preference_name()
        constraints = cls.get_value_constraints(overrides)

        cache_key = (cls, json_dumps(constraints, sort_keys=True, default=str))
        if cache_key not in _VALUE_VALIDATOR_CLASSES:
            value_annotation = cls.model_fields["value"].annotation
            try:
                _VALUE_VALIDATOR_CLASSES[cache_key] = create_model(
                    f"{preference_name}ValueValidator",
                    __base__=BaseModel,
                    value=(Annotated[value_annotation, Field(**constraints)], ...),
                )
            except SchemaError as e:
                # a constraint whose value is malformed (wrong type, invalid regex, ...)
                raise InvalidValueConstraintsError(preference_name, f"{e}") from e
        return _VALUE_VALIDATOR_CLASSES[cache_key]

    @classmethod
    def validate_value(cls, value: Any, overrides: dict[str, Any] | None = None) -> None:
        validator_class = cls.build_value_validator(overrides)
        try:
            validator_class(value=value)
        except TypeError as e:
            # pydantic reports a constraint that cannot apply to the field type only on use
            raise InvalidValueConstraintsError(cls.get_preference_name(), f"{e}") from e

    @classmethod
    def get_preference_class_from_name(cls, preference_name: PreferenceName) -> type[Self]:
        # NOTE: the registry is untyped (`dict[str, type]`), the annotation below narrows it
        preference_class: type[Self] | None = cls.registered_user_preference_classes.get(preference_name, None)
        if preference_class is None:
            raise NoPreferenceFoundError(preference_name)
        return preference_class

    @classmethod
    def get_preference_name(cls) -> PreferenceName:
        # NOTE: this will be `unique` among all subclasses.
        # No class inherited from this one, can be defined using the same name,
        # even if the context is different.
        return cls.__name__

    @classmethod
    def get_default_value(cls) -> Any:
        value_field: FieldInfo = dict(cls.model_fields)["value"]

        return (
            value_field.default_factory()  # type: ignore[call-arg]
            if callable(value_field.default_factory)
            else value_field.default
        )


class FrontendUserPreference(_BaseUserPreferenceModel):
    preference_type: Literal[PreferenceType.FRONTEND] = PreferenceType.FRONTEND

    preference_identifier: PreferenceIdentifier = Field(..., description="used by the frontend")

    value: Any

    def to_db(self) -> dict:
        return self.model_dump(exclude={"preference_identifier", "preference_type"})

    @classmethod
    def update_preference_default_value(cls, new_default: Any) -> None:
        # pylint: disable=unsubscriptable-object
        expected_type = get_type(cls.model_fields["value"])
        detected_type = type(new_default)
        if expected_type != detected_type:
            msg = f"Error, {cls.__name__} {expected_type=} differs from {detected_type=}"
            raise TypeError(msg)

        if cls.model_fields["value"].default is None:
            cls.model_fields["value"].default_factory = lambda: new_default
        else:
            cls.model_fields["value"].default = new_default
            cls.model_fields["value"].default_factory = None

        cls.model_rebuild(force=True)


class UserServiceUserPreference(_BaseUserPreferenceModel):
    preference_type: Literal[PreferenceType.USER_SERVICE] = PreferenceType.USER_SERVICE

    service_key: ServiceKey = Field(..., description="the service which manages the preferences")
    service_version: ServiceVersion = Field(..., description="version of the service which manages the preference")

    def to_db(self) -> dict:
        return self.model_dump(exclude={"preference_type"})


type AnyUserPreference = Annotated[
    FrontendUserPreference | UserServiceUserPreference,
    Field(discriminator="preference_type"),
]
