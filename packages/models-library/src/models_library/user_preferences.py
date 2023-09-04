from enum import auto
from pathlib import Path
from typing import Annotated, Any, ClassVar, TypeAlias

from pydantic import BaseModel, Field
from pydantic.main import ModelMetaclass

from .services import ServiceKey, ServiceVersion
from .utils.enums import StrAutoEnum

# NOTE: for pydantic-2 from pydantic._internal.import _model_construction
# use _model_construction.ModelMetaclass instead!


class _AutoRegisterMeta(ModelMetaclass):
    _registered_user_preference_classes: ClassVar[dict[str, type]] = {}

    def __new__(cls, name, bases, attrs, *args, **kwargs):
        new_class = super().__new__(cls, name, bases, attrs, *args, **kwargs)

        if name != cls.__name__:
            if name in cls._registered_user_preference_classes:
                msg = (
                    f"Class named '{name}' was already defined at "
                    f"{cls._registered_user_preference_classes[name]}."
                    " Please choose a different class name!"
                )
                raise TypeError(msg)
            cls._registered_user_preference_classes[name] = new_class

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
        ] | None = cls._registered_user_preference_classes.get(preference_name, None)
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
            cls.__fields__["value"].default_factory()
            if cls.__fields__["value"].default_factory
            else cls.__fields__["value"].default
        )


class FrontendUserPreference(_BaseUserPreferenceModel):
    preference_type: PreferenceType = Field(default=PreferenceType.FRONTEND, const=True)

    preference_identifier: PreferenceIdentifier = Field(
        ..., description="used by the frontend"
    )

    def to_db(self) -> dict:
        return self.dict(exclude={"preference_identifier", "preference_type"})


class UserServiceUserPreference(_BaseUserPreferenceModel):
    preference_type: PreferenceType = Field(PreferenceType.USER_SERVICE, const=True)

    service_key: ServiceKey = Field(
        ..., description="the service which manages the preferences"
    )
    service_version: ServiceVersion = Field(
        ..., description="version of the service which manages the preference"
    )
    file_path: Path = Field(
        ..., description="path of the file where the preference is stored"
    )

    def to_db(self) -> dict:
        return self.dict(exclude={"preference_type"})


AnyUserPreference: TypeAlias = Annotated[
    FrontendUserPreference | UserServiceUserPreference,
    Field(discriminator="preference_type"),
]
