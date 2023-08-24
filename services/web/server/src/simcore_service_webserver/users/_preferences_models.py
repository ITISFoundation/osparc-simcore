from models_library.user_preferences import (
    BaseFrontendUserPreference,
    PreferenceWidgetType,
)


class ConfirmationBackToDashboardFrontendUserPreference(BaseFrontendUserPreference):
    widget_type: PreferenceWidgetType = PreferenceWidgetType.CHECKBOX
    display_label: str = "Go back to Dashboard"
    tooltip_message: str = (
        "If checked, asks for confirmation when the user goes back to the dashboard"
    )
    value: bool = True


class ConfirmationDeleteStudyFrontendUserPreference(BaseFrontendUserPreference):
    widget_type: PreferenceWidgetType = PreferenceWidgetType.CHECKBOX
    display_label: str = "Delete a study"
    tooltip_message: str = "If checked, asks for confirmation before deleting a study"
    value: bool = True


class ConfirmationDeleteNodeFrontendUserPreference(BaseFrontendUserPreference):
    widget_type: PreferenceWidgetType = PreferenceWidgetType.CHECKBOX
    display_label: str = "Delete a Node"
    tooltip_message: str = "If checked, asks for confirmation before deleting a Node"
    value: bool = True


class ConfirmationStopNodeFrontendUserPreference(BaseFrontendUserPreference):
    widget_type: PreferenceWidgetType = PreferenceWidgetType.CHECKBOX
    display_label: str = "Stop Node"
    tooltip_message: str = "If checked, asks for confirmation before stopping a Node"
    value: bool = True


class SnapNodeToGridFrontendUserPreference(BaseFrontendUserPreference):
    widget_type: PreferenceWidgetType = PreferenceWidgetType.CHECKBOX
    display_label: str = "Snap Node to grid"
    tooltip_message: str = "If checked Nodes will be automatically snapped to a grid"
    value: bool = True


class ConnectPortsAutomaticallyFrontendUserPreference(BaseFrontendUserPreference):
    widget_type: PreferenceWidgetType = PreferenceWidgetType.CHECKBOX
    display_label: str = "Connect ports automatically"
    tooltip_message: str = (
        "If checked ports will be connected automatically based "
        "on their supported types and the order in which they appear"
    )
    value: bool = True


ALL_FRONTEND_PREFERENCES: list[type[BaseFrontendUserPreference]] = [
    ConfirmationBackToDashboardFrontendUserPreference,
    ConfirmationDeleteStudyFrontendUserPreference,
    ConfirmationDeleteNodeFrontendUserPreference,
    ConfirmationStopNodeFrontendUserPreference,
    SnapNodeToGridFrontendUserPreference,
    ConnectPortsAutomaticallyFrontendUserPreference,
]
