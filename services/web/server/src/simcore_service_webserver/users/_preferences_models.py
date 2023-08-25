from models_library.services_ui import WidgetType
from models_library.user_preferences import (
    BaseFrontendUserPreference,
    PreferenceName,
    ValueType,
)
from pydantic import Field


class ConfirmationBackToDashboardFrontendUserPreference(BaseFrontendUserPreference):
    render_widget = True
    widget_type = WidgetType.CheckBox
    display_label = "Go back to Dashboard"
    tooltip_message = (
        "If checked, asks for confirmation when the user goes back to the dashboard"
    )
    value_type = ValueType.BOOL
    value: bool = True


class ConfirmationDeleteStudyFrontendUserPreference(BaseFrontendUserPreference):
    render_widget = True
    widget_type = WidgetType.CheckBox
    display_label = "Delete a study"
    tooltip_message = "If checked, asks for confirmation before deleting a study"
    value_type = ValueType.BOOL
    value: bool = True


class ConfirmationDeleteNodeFrontendUserPreference(BaseFrontendUserPreference):
    render_widget = True
    widget_type = WidgetType.CheckBox
    display_label = "Delete a Node"
    tooltip_message = "If checked, asks for confirmation before deleting a Node"
    value_type = ValueType.BOOL
    value: bool = True


class ConfirmationStopNodeFrontendUserPreference(BaseFrontendUserPreference):
    render_widget = True
    widget_type = WidgetType.CheckBox
    display_label = "Stop Node"
    tooltip_message = "If checked, asks for confirmation before stopping a Node"
    value_type = ValueType.BOOL
    value: bool = True


class SnapNodeToGridFrontendUserPreference(BaseFrontendUserPreference):
    render_widget = True
    widget_type = WidgetType.CheckBox
    display_label = "Snap Node to grid"
    tooltip_message = "If checked Nodes will be automatically snapped to a grid"
    value_type = ValueType.BOOL
    value: bool = True


class ConnectPortsAutomaticallyFrontendUserPreference(BaseFrontendUserPreference):
    render_widget = True
    widget_type = WidgetType.CheckBox
    display_label = "Connect ports automatically"
    tooltip_message = (
        "If checked ports will be connected automatically based "
        "on their supported types and the order in which they appear"
    )
    value_type = ValueType.BOOL
    value: bool = True


class ServicesFrontendUserPreference(BaseFrontendUserPreference):
    render_widget: bool = False
    widget_type: WidgetType | None = None
    display_label: str | None = None
    tooltip_message: str | None = None

    value_type = ValueType.DICT
    value: dict = Field(default_factory=dict)

    @classmethod
    def get_preference_name(cls) -> PreferenceName:
        return "services"


class ThemeNameFrontendUserPreference(BaseFrontendUserPreference):
    render_widget: bool = False
    widget_type: WidgetType | None = None
    display_label: str | None = None
    tooltip_message: str | None = None

    value_type = ValueType.STR
    value: str | None = None

    @classmethod
    def get_preference_name(cls) -> PreferenceName:
        return "themeName"


class LastVcsRefUIFrontendUserPreference(BaseFrontendUserPreference):
    render_widget: bool = False
    widget_type: WidgetType | None = None
    display_label: str | None = None
    tooltip_message: str | None = None

    value_type = ValueType.STR
    value: str | None = None

    @classmethod
    def get_preference_name(cls) -> PreferenceName:
        return "lastVcsRefUI"


ALL_FRONTEND_PREFERENCES: list[type[BaseFrontendUserPreference]] = [
    ConfirmationBackToDashboardFrontendUserPreference,
    ConfirmationDeleteStudyFrontendUserPreference,
    ConfirmationDeleteNodeFrontendUserPreference,
    ConfirmationStopNodeFrontendUserPreference,
    SnapNodeToGridFrontendUserPreference,
    ConnectPortsAutomaticallyFrontendUserPreference,
    ServicesFrontendUserPreference,
    ThemeNameFrontendUserPreference,
    LastVcsRefUIFrontendUserPreference,
]
