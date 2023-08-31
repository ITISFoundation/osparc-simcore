from models_library.user_preferences import (
    BaseFrontendUserPreference,
    PreferenceIdentifier,
    PreferenceName,
)
from pydantic import Field


class ConfirmationBackToDashboardFrontendUserPreference(BaseFrontendUserPreference):
    preference_identifier = "confirmBackToDashboard"
    value: bool = True


class ConfirmationDeleteStudyFrontendUserPreference(BaseFrontendUserPreference):
    preference_identifier = "confirmDeleteStudy"
    value: bool = True


class ConfirmationDeleteNodeFrontendUserPreference(BaseFrontendUserPreference):
    preference_identifier = "confirmDeleteNode"
    value: bool = True


class ConfirmationStopNodeFrontendUserPreference(BaseFrontendUserPreference):
    preference_identifier = "confirmStopNode"
    value: bool = True


class SnapNodeToGridFrontendUserPreference(BaseFrontendUserPreference):
    preference_identifier = "snapNodeToGrid"
    value: bool = True


class ConnectPortsAutomaticallyFrontendUserPreference(BaseFrontendUserPreference):
    preference_identifier = "autoConnectPorts"
    value: bool = True


class DoNotShowAnnouncementsFrontendUserPreference(BaseFrontendUserPreference):
    preference_identifier = "dontShowAnnouncements"
    value: list = Field(default_factory=list)


class ServicesFrontendUserPreference(BaseFrontendUserPreference):
    preference_identifier = "services"
    value: dict = Field(default_factory=dict)


class ThemeNameFrontendUserPreference(BaseFrontendUserPreference):
    preference_identifier = "themeName"
    value: str | None = None


class LastVcsRefUIFrontendUserPreference(BaseFrontendUserPreference):
    preference_identifier = "lastVcsRefUI"
    value: str | None = None


class PreferredWalletIdFrontendUserPreference(BaseFrontendUserPreference):
    preference_identifier = "preferredWalletId"
    value: int | None = None


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
    PreferredWalletIdFrontendUserPreference,
]


def get_preference_identifier_to_preference_name_map() -> (
    dict[PreferenceIdentifier, PreferenceName]
):
    mapping: dict[PreferenceIdentifier, str] = {}
    for preference in ALL_FRONTEND_PREFERENCES:
        preference_identifier = preference.__fields__["preference_identifier"].default
        mapping[preference_identifier] = preference.get_preference_name()

    return mapping
