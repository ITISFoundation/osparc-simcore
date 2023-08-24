from typing import TypeAlias

from pydantic import BaseModel

from ..user_preferences import PreferenceName, PreferenceWidgetType

# NOTE: this field needs to be a tuple of all the field
# types defined inside `_preferences_models.py`
ValueType: TypeAlias = bool


class UserPreference(BaseModel):
    widget_type: PreferenceWidgetType
    display_label: str
    tooltip_message: str

    value: ValueType


UserPreferencesGet: TypeAlias = dict[PreferenceName, UserPreference]


class UserPreferencePatchRequestBody(BaseModel):
    value: ValueType


class UserPreferencePatchPathParams(BaseModel):
    preference_name: PreferenceName
