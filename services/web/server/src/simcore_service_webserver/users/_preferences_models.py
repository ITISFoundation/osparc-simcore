from models_library.user_preferences import (
    FrontendUserPreference,
    PreferenceIdentifier,
    PreferenceName,
)
from pydantic import Field


class ConfirmationBackToDashboardFrontendUserPreference(FrontendUserPreference):
    preference_identifier = "confirmBackToDashboard"
    value: bool = True


class ConfirmationDeleteStudyFrontendUserPreference(FrontendUserPreference):
    preference_identifier = "confirmDeleteStudy"
    value: bool = True


class ConfirmationDeleteNodeFrontendUserPreference(FrontendUserPreference):
    preference_identifier = "confirmDeleteNode"
    value: bool = True


class ConfirmationStopNodeFrontendUserPreference(FrontendUserPreference):
    preference_identifier = "confirmStopNode"
    value: bool = True


class SnapNodeToGridFrontendUserPreference(FrontendUserPreference):
    preference_identifier = "snapNodeToGrid"
    value: bool = True


class ConnectPortsAutomaticallyFrontendUserPreference(FrontendUserPreference):
    preference_identifier = "autoConnectPorts"
    value: bool = True


class DoNotShowAnnouncementsFrontendUserPreference(FrontendUserPreference):
    preference_identifier = "dontShowAnnouncements"
    value: list = Field(default_factory=list)


class ServicesFrontendUserPreference(FrontendUserPreference):
    preference_identifier = "services"
    value: dict = Field(default_factory=dict)


class ThemeNameFrontendUserPreference(FrontendUserPreference):
    preference_identifier = "themeName"
    value: str | None = None


class LastVcsRefUIFrontendUserPreference(FrontendUserPreference):
    preference_identifier = "lastVcsRefUI"
    value: str | None = None


class PreferredWalletIdFrontendUserPreference(FrontendUserPreference):
    preference_identifier = "preferredWalletId"
    value: int | None = None


class UserInactivityThresholdFrontendUserPreference(FrontendUserPreference):
    preference_identifier = "userInactivityThreshold"
    value: int | None = 45 * 3600  # in seconds


ALL_FRONTEND_PREFERENCES: list[type[FrontendUserPreference]] = [
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
    PreferredWalletIdFrontendUserPreference,
    UserInactivityThresholdFrontendUserPreference,
]


def get_preference_identifier_to_preference_name_map() -> (
    dict[PreferenceIdentifier, PreferenceName]
):
    mapping: dict[PreferenceIdentifier, str] = {}
    for preference in ALL_FRONTEND_PREFERENCES:
        preference_identifier = preference.__fields__["preference_identifier"].default
        mapping[preference_identifier] = preference.get_preference_name()

    return mapping
