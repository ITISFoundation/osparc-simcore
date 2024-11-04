from enum import auto
from typing import Annotated, Any, ClassVar, Literal, TypeAlias

from common_library.pydantic_fields_extension import get_type
from pydantic import BaseModel, Field
from pydantic._internal._model_construction import ModelMetaclass

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


PreferenceName: TypeAlias = str
PreferenceIdentifier: TypeAlias = str


class _ExtendedBaseModel(BaseModel, metaclass=_AutoRegisterMeta):
    ...


class PreferenceType(StrAutoEnum):
    FRONTEND = auto()
    USER_SERVICE = auto()


class NoPreferenceFoundError(RuntimeError):
    def __init__(self, preference_name) -> None:
        self.preference_name = preference_name
        super().__init__(f"No preference class found for provided {preference_name=}")


class _BaseUserPreferenceModel(_ExtendedBaseModel):
    preference_type: PreferenceType = Field(
        ..., description="distinguish between the types of preferences"
    )

    value: Any = Field(..., description="value of the preference")

    @classmethod
    def get_preference_class_from_name(
        cls, preference_name: PreferenceName
    ) -> type["_BaseUserPreferenceModel"]:
        preference_class: type[
            "_BaseUserPreferenceModel"
        ] | None = cls.registered_user_preference_classes.get(preference_name, None)
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
        return (
            cls.model_fields["value"].default_factory()
            if cls.model_fields["value"].default_factory
            else cls.model_fields["value"].default
        )


class FrontendUserPreference(_BaseUserPreferenceModel):
    preference_type: Literal[PreferenceType.FRONTEND] = PreferenceType.FRONTEND

    preference_identifier: PreferenceIdentifier = Field(
        ..., description="used by the frontend"
    )

    value: Any

    def to_db(self) -> dict:
        return self.model_dump(exclude={"preference_identifier", "preference_type"})

    @classmethod
    def update_preference_default_value(cls, new_default: Any) -> None:
        expected_type = get_type(cls.model_fields["value"])
        detected_type = type(new_default)
        if expected_type != detected_type:
            msg = (
                f"Error, {cls.__name__} {expected_type=} differs from {detected_type=}"
            )
            raise TypeError(msg)

        if cls.model_fields["value"].default is None:
            cls.model_fields["value"].default_factory = lambda: new_default
        else:
            cls.model_fields["value"].default = new_default
            cls.model_fields["value"].default_factory = None

        cls.model_rebuild(force=True)


class UserServiceUserPreference(_BaseUserPreferenceModel):
    preference_type: Literal[PreferenceType.USER_SERVICE] = PreferenceType.USER_SERVICE

    service_key: ServiceKey = Field(
        ..., description="the service which manages the preferences"
    )
    service_version: ServiceVersion = Field(
        ..., description="version of the service which manages the preference"
    )

    def to_db(self) -> dict:
        return self.model_dump(exclude={"preference_type"})


AnyUserPreference: TypeAlias = Annotated[
    FrontendUserPreference | UserServiceUserPreference,
    Field(discriminator="preference_type"),
]
