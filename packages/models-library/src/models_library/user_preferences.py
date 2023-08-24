from enum import auto
from typing import Any, ClassVar, TypeAlias

from pydantic import BaseModel, Field
from pydantic.main import ModelMetaclass

from .services import ServiceKey
from .utils.enums import StrAutoEnum


class _AutoRegisterMeta(ModelMetaclass):
    _registered_user_preference_classes: ClassVar[dict[str, type]] = {}

    def __new__(cls, name, bases, attrs):
        new_class = super().__new__(cls, name, bases, attrs)

        if name != BaseModel.__name__:
            if name in cls._registered_user_preference_classes:
                msg = (
                    f"Class named '{name}' was already defined at "
                    f"{cls._registered_user_preference_classes[name]}."
                    " Please choose a different class name!"
                )
                raise TypeError(msg)
            cls._registered_user_preference_classes[name] = new_class

        return new_class


class _ExtendedBaseModel(BaseModel, metaclass=_AutoRegisterMeta):
    ...


class PreferenceType(StrAutoEnum):
    BACKEND = auto()
    FRONTEND = auto()
    USER_SERVICE = auto()


class PreferenceWidgetType(StrAutoEnum):
    CHECKBOX = auto()


class _BaseUserPreferenceModel(_ExtendedBaseModel):
    preference_type: PreferenceType = Field(
        ..., description="distinguish between the types of preferences"
    )

    value: Any | None = Field(
        ...,
        description="the value of the preference. Stored as is and cannot be queried over",
    )

    @classmethod
    def get_preference_name(cls) -> str:
        # NOTE: this will be `unique` among all subclasses.
        # No class inherited from this one, can be defined using the same name,
        # even if the context is different.
        return cls.__name__


class BaseBackendUserPreference(_BaseUserPreferenceModel):
    preference_type: PreferenceType = PreferenceType.BACKEND


class BaseFrontendUserPreference(_BaseUserPreferenceModel):
    preference_type: PreferenceType = PreferenceType.FRONTEND

    # NOTE: below fields do not require storage in the DB
    widget_type: PreferenceWidgetType = Field(
        ..., description="type of widget to display in the frontend"
    )
    display_label: str = Field(..., description="short label to display")
    tooltip_message: str = Field(
        ..., description="more information to display when hovering"
    )


class BaseUserServiceUserPreference(_BaseUserPreferenceModel):
    preference_type: PreferenceType = PreferenceType.USER_SERVICE

    # NOTE: preferences are stored per service and the version is not considered
    service_key: ServiceKey = Field(
        ..., description="the service which manages the preferences"
    )

    # NOTE: below fields do not require storage in the DB
    last_changed_utc_timestamp: float = Field(
        ...,
        description="needs to be provided to signal that the value of the property changed",
    )


AnyBaseUserPreference: TypeAlias = (
    BaseBackendUserPreference
    | BaseFrontendUserPreference
    | BaseUserServiceUserPreference
)
