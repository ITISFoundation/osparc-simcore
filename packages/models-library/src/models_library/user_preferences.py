from collections.abc import Mapping
from enum import Enum, auto
from typing import Any, ClassVar, TypeAlias

from pydantic import BaseModel, Field
from pydantic.main import ModelMetaclass

from .services import ServiceKey
from .services_ui import WidgetType
from .utils.enums import StrAutoEnum

IntStr: TypeAlias = int | str
DictStrAny = dict[str, Any]
AbstractSetIntStr: TypeAlias = set[IntStr]
MappingIntStrAny: TypeAlias = Mapping[IntStr, Any]


# NOTE: for pyndatic-2 from pydantic._internal.import _model_construction
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


class _ExtendedBaseModel(BaseModel, metaclass=_AutoRegisterMeta):
    ...


class ValueType(str, Enum):
    BOOL = "boolean"
    STR = "string"
    FLOAT = "number"
    INT = "integer"
    LIST = "array"
    DICT = "dictionary"


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
        cls, preference_name: str
    ) -> "_BaseUserPreferenceModel":
        preference_class: "_BaseUserPreferenceModel" | None = (
            cls._registered_user_preference_classes.get(preference_name, None)
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


class BaseBackendUserPreference(_BaseUserPreferenceModel):
    preference_type: PreferenceType = PreferenceType.BACKEND

    class Config:
        exclude_from_serialization: ClassVar[set[str]] = {
            "preference_type",
        }


class BaseFrontendUserPreference(_BaseUserPreferenceModel):
    preference_type: PreferenceType = PreferenceType.FRONTEND

    # NOTE: below fields do not require storage in the DB
    preference_identifier: str = Field(..., description="used by the frontend client")
    expose_in_preferences: bool = Field(
        ..., description="when True a widget will automatically be rendered"
    )
    value_type: ValueType = Field(..., description="content type of the value")
    widget_type: WidgetType | None = Field(
        ..., description="type of widget to display in the frontend"
    )
    label: str | None = Field(..., description="user readable name for the preference")
    description: str | None = Field(
        ..., description="more information about this preference"
    )

    class Config:
        exclude_from_serialization: ClassVar[set[str]] = {
            "description",
            "expose_in_preferences",
            "label",
            "preference_identifier",
            "preference_type",
            "value_type",
            "widget_type",
        }


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

    class Config:
        exclude_from_serialization: ClassVar[set[str]] = {
            "last_changed_utc_timestamp",
            "preference_type",
        }


AnyBaseUserPreference: TypeAlias = (
    BaseBackendUserPreference
    | BaseFrontendUserPreference
    | BaseUserServiceUserPreference
)
