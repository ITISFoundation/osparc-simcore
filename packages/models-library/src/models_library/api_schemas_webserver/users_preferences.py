from typing import Any, TypeAlias

from pydantic import BaseModel

from ..services_ui import WidgetType
from ..user_preferences import PreferenceName, ValueType


class UserPreference(BaseModel):
    render_widget: bool
    widget_type: WidgetType
    display_label: str
    tooltip_message: str
    value_type: ValueType
    value: Any


UserPreferencesGet: TypeAlias = dict[PreferenceName, UserPreference]


class UserPreferencePatchRequestBody(BaseModel):
    value: Any


class UserPreferencePatchPathParams(BaseModel):
    preference_name: PreferenceName
