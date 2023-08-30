from models_library.services_ui import WidgetType
from models_library.user_preferences import BaseFrontendUserPreference, ValueType
from pydantic import Field


class ConfirmationBackToDashboardFrontendUserPreference(BaseFrontendUserPreference):
    expose_in_preferences = True
    widget_type = WidgetType.CheckBox
    label = "Go back to Dashboard"
    description = (
        "If checked, asks for confirmation when the user goes back to the dashboard"
    )

    preference_identifier = "confirmBackToDashboard"
    value_type = ValueType.BOOL
    value: bool = True


class ConfirmationDeleteStudyFrontendUserPreference(BaseFrontendUserPreference):
    expose_in_preferences = True
    widget_type = WidgetType.CheckBox
    label = "Delete a study"
    description = "If checked, asks for confirmation before deleting a study"

    preference_identifier = "confirmDeleteStudy"
    value_type = ValueType.BOOL
    value: bool = True


class ConfirmationDeleteNodeFrontendUserPreference(BaseFrontendUserPreference):
    expose_in_preferences = True
    widget_type = WidgetType.CheckBox
    label = "Delete a Node"
    description = "If checked, asks for confirmation before deleting a Node"

    preference_identifier = "confirmDeleteNode"
    value_type = ValueType.BOOL
    value: bool = True


class ConfirmationStopNodeFrontendUserPreference(BaseFrontendUserPreference):
    expose_in_preferences = True
    widget_type = WidgetType.CheckBox
    label = "Stop Node"
    description = "If checked, asks for confirmation before stopping a Node"

    preference_identifier = "confirmStopNode"
    value_type = ValueType.BOOL
    value: bool = True


class SnapNodeToGridFrontendUserPreference(BaseFrontendUserPreference):
    expose_in_preferences = True
    widget_type = WidgetType.CheckBox
    label = "Snap Node to grid"
    description = "If checked Nodes will be automatically snapped to a grid"

    preference_identifier = "snapNodeToGrid"
    value_type = ValueType.BOOL
    value: bool = True


class ConnectPortsAutomaticallyFrontendUserPreference(BaseFrontendUserPreference):
    expose_in_preferences = True
    widget_type = WidgetType.CheckBox
    label = "Connect ports automatically"
    description = (
        "If checked ports will be connected automatically based "
        "on their supported types and the order in which they appear"
    )
    preference_identifier = "autoConnectPorts"
    value_type = ValueType.BOOL
    value: bool = True


class DoNotShowAnnouncementsFrontendUserPreference(BaseFrontendUserPreference):
    expose_in_preferences: bool = False
    widget_type: WidgetType | None = None
    label: str | None = None
    description: str | None = None

    preference_identifier = "dontShowAnnouncements"
    value_type = ValueType.LIST
    value: list = Field(default_factory=list)


class ServicesFrontendUserPreference(BaseFrontendUserPreference):
    expose_in_preferences: bool = False
    widget_type: WidgetType | None = None
    label: str | None = None
    description: str | None = None

    preference_identifier = "services"
    value_type = ValueType.DICT
    value: dict = Field(default_factory=dict)


class ThemeNameFrontendUserPreference(BaseFrontendUserPreference):
    expose_in_preferences: bool = False
    widget_type: WidgetType | None = None
    label: str | None = None
    description: str | None = None

    preference_identifier = "themeName"
    value_type = ValueType.STR
    value: str | None = None


class LastVcsRefUIFrontendUserPreference(BaseFrontendUserPreference):
    expose_in_preferences: bool = False
    widget_type: WidgetType | None = None
    label: str | None = None
    description: str | None = None

    preference_identifier = "lastVcsRefUI"
    value_type = ValueType.STR
    value: str | None = None


ALL_FRONTEND_PREFERENCES: list[type[BaseFrontendUserPreference]] = [
    ConfirmationBackToDashboardFrontendUserPreference,
    ConfirmationDeleteStudyFrontendUserPreference,
    ConfirmationDeleteNodeFrontendUserPreference,
    ConfirmationStopNodeFrontendUserPreference,
    SnapNodeToGridFrontendUserPreference,
    ConnectPortsAutomaticallyFrontendUserPreference,
    DoNotShowAnnouncementsFrontendUserPreference,
    ServicesFrontendUserPreference,
    ThemeNameFrontendUserPreference,
    LastVcsRefUIFrontendUserPreference,
]


def get_preference_name_to_class_name_map() -> dict[str, str]:
    mapping: dict[str, str] = {}
    for preference in ALL_FRONTEND_PREFERENCES:
        preference_name = preference.__fields__["preference_identifier"].default
        preference_class_name = preference.__name__
        mapping[preference_name] = preference_class_name

    return mapping
