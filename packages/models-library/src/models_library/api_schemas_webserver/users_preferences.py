from typing import Any, TypeAlias

from pydantic import BaseModel

from ..services_ui import WidgetType
from ..user_preferences import PreferenceName, ValueType


class UserPreference(BaseModel):
    render_widget: bool
    widget_type: WidgetType | None
    display_label: str | None
    tooltip_message: str | None

    value_type: ValueType
    value: Any


UserPreferencesGet: TypeAlias = dict[PreferenceName, UserPreference]


class UserPreferencePatchRequestBody(BaseModel):
    value: Any


class UserPreferencePatchPathParams(BaseModel):
    preference_name: PreferenceName
