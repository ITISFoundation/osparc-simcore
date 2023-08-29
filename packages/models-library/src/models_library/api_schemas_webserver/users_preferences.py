from typing import Any, TypeAlias

from pydantic import BaseModel, Field

from ..services_ui import WidgetType
from ..user_preferences import PreferenceName, ValueType


class UserPreference(BaseModel):
    render_widget: bool = Field(default=..., alias="exposeInPreferences")
    widget_type: WidgetType | None = Field(default=..., alias="widget")
    display_label: str | None = Field(default=..., alias="label")
    tooltip_message: str | None = Field(default=..., alias="description")

    value_type: ValueType = Field(default=..., alias="type")
    default_value: Any = Field(default=..., alias="defaultValue")
    value: Any

    class Config:
        allow_population_by_field_name = True


UserPreferencesGet: TypeAlias = dict[PreferenceName, UserPreference]


class UserPreferencePatchRequestBody(BaseModel):
    value: Any


class UserPreferencePatchPathParams(BaseModel):
    frontend_preference_name: PreferenceName
