from collections.abc import Mapping
from enum import auto
from pathlib import Path
from typing import Any, ClassVar, TypeAlias

from pydantic import BaseModel, Field
from pydantic.main import ModelMetaclass

from .services import ServiceKey
from .utils.enums import StrAutoEnum

# NOTE: these match the definitions insidepydantic's internals,
# which cannot be imported (defined under TYPE_CHECKING)
IntStr: TypeAlias = int | str
DictStrAny = dict[str, Any]
AbstractSetIntStr: TypeAlias = set[IntStr]
MappingIntStrAny: TypeAlias = Mapping[IntStr, Any]


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
    BACKEND = auto()
    FRONTEND = auto()
    USER_SERVICE = auto()


class NoPreferenceFoundError(RuntimeError):
    ...


class _BaseUserPreferenceModel(_ExtendedBaseModel):
    preference_type: PreferenceType = Field(
        ..., description="distinguish between the types of preferences"
    )

    value: Any = Field(
        ...,
        description="the value of the preference. Stored as is and cannot be queried over",
    )

    @classmethod
    def get_preference_class_from_name(
        cls, preference_name: PreferenceName
    ) -> type["_BaseUserPreferenceModel"]:
        preference_class: type[
            "_BaseUserPreferenceModel"
        ] | None = cls._registered_user_preference_classes.get(
            preference_name, None
        )  # type: ignore
        if preference_class is None:
            msg = f"No preference class found for provided {preference_name=}"
            raise NoPreferenceFoundError(msg)
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

    def dict(  # noqa: A003
        self,
        *,
        include: AbstractSetIntStr | MappingIntStrAny = None,  # type: ignore
        exclude: AbstractSetIntStr | MappingIntStrAny = None,  # type: ignore
        by_alias: bool = False,
        skip_defaults: bool = None,  # type: ignore  # noqa: RUF013
        exclude_unset: bool = False,
        exclude_defaults: bool = False,
        exclude_none: bool = False,
    ) -> DictStrAny:
        if exclude is None:
            config_class = getattr(self, "Config", None)
            exclude_from_serialization: set | None = getattr(
                config_class, "exclude_from_serialization", None
            )
            if exclude_from_serialization:
                exclude = exclude_from_serialization
        return super().dict(
            include=include,
            exclude=exclude,
            by_alias=by_alias,
            skip_defaults=skip_defaults,
            exclude_unset=exclude_unset,
            exclude_defaults=exclude_defaults,
            exclude_none=exclude_none,
        )


class FrontendUserPreference(_BaseUserPreferenceModel):
    preference_type: PreferenceType = Field(
        default=PreferenceType.FRONTEND, frozen=True
    )

    preference_identifier: PreferenceIdentifier = Field(
        ..., description="used by the frontend"
    )

    class Config:
        exclude_from_serialization: ClassVar[set[str]] = {
            "preference_identifier",
            "preference_type",
        }


class UserServiceUserPreference(_BaseUserPreferenceModel):
    preference_type: PreferenceType = Field(PreferenceType.USER_SERVICE, frozen=True)

    # NOTE: preferences are stored per service and the version is not considered
    service_key: ServiceKey = Field(
        ..., description="the service which manages the preferences"
    )
    file_path: Path = Field(..., description="path of the file")

    class Config:
        exclude_from_serialization: ClassVar[set[str]] = {
            "preference_type",
            "service_key",
        }


AnyUserPreference: TypeAlias = FrontendUserPreference | UserServiceUserPreference
