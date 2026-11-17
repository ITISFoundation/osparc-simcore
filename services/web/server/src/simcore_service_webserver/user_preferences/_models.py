from aiohttp import web
from models_library.shared_user_preferences import (
    AllowMetricsCollectionFrontendUserPreference,
    BillingCenterUsageColumnOrderFrontendUserPreference,
    ConfirmationBackToDashboardFrontendUserPreference,
    ConfirmationDeleteNodeFrontendUserPreference,
    ConfirmationDeleteStudyFrontendUserPreference,
    ConfirmationStopNodeFrontendUserPreference,
    ConnectPortsAutomaticallyFrontendUserPreference,
    CreditsWarningThresholdFrontendUserPreference,
    DoNotShowAnnouncementsFrontendUserPreference,
    JobConcurrencyLimitFrontendUserPreference,
    LastVcsRefUIFrontendUserPreference,
    PreferredWalletIdFrontendUserPreference,
    ServicesFrontendUserPreference,
    SnapNodeToGridFrontendUserPreference,
    TelemetryLowDiskSpaceWarningThresholdFrontendUserPreference,
    ThemeNameFrontendUserPreference,
    TwoFAFrontendUserPreference,
    UserInactivityThresholdFrontendUserPreference,
    WalletIndicatorVisibilityFrontendUserPreference,
)
from models_library.user_preferences import (
    FrontendUserPreference,
    PreferenceIdentifier,
    PreferenceName,
)

from ..users.settings import UsersSettings, get_plugin_settings

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
    CreditsWarningThresholdFrontendUserPreference,
    WalletIndicatorVisibilityFrontendUserPreference,
    UserInactivityThresholdFrontendUserPreference,
    JobConcurrencyLimitFrontendUserPreference,
    AllowMetricsCollectionFrontendUserPreference,
    TelemetryLowDiskSpaceWarningThresholdFrontendUserPreference,
    TwoFAFrontendUserPreference,
    BillingCenterUsageColumnOrderFrontendUserPreference,
]

_PREFERENCE_NAME_TO_IDENTIFIER_MAPPING: dict[PreferenceName, PreferenceIdentifier] = {
    p.get_preference_name(): p.model_fields["preference_identifier"].default for p in ALL_FRONTEND_PREFERENCES
}
_PREFERENCE_IDENTIFIER_TO_NAME_MAPPING: dict[PreferenceIdentifier, PreferenceName] = {
    i: n for n, i in _PREFERENCE_NAME_TO_IDENTIFIER_MAPPING.items()
}


def get_preference_name(preference_identifier: PreferenceIdentifier) -> PreferenceName:
    return _PREFERENCE_IDENTIFIER_TO_NAME_MAPPING[preference_identifier]


def get_preference_identifier(preference_name: PreferenceName) -> PreferenceIdentifier:
    return _PREFERENCE_NAME_TO_IDENTIFIER_MAPPING[preference_name]


def overwrite_user_preferences_defaults(app: web.Application) -> None:
    settings: UsersSettings = get_plugin_settings(app)

    search_map: dict[str, type[FrontendUserPreference]] = {x.__name__: x for x in ALL_FRONTEND_PREFERENCES}

    for (
        preference_class,
        value,
    ) in settings.USERS_FRONTEND_PREFERENCES_DEFAULTS_OVERWRITES.items():
        search_map[preference_class].update_preference_default_value(value)
