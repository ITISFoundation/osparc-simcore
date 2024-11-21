from typing import Final

from aiohttp import web
from models_library.authentification import TwoFactorAuthentificationMethod
from models_library.shared_user_preferences import (
    AllowMetricsCollectionFrontendUserPreference,
)
from models_library.user_preferences import (
    FrontendUserPreference,
    PreferenceIdentifier,
    PreferenceName,
)
from pydantic import Field, NonNegativeInt

from .settings import UsersSettings, get_plugin_settings

_MINUTE: Final[NonNegativeInt] = 60


class ConfirmationBackToDashboardFrontendUserPreference(FrontendUserPreference):
    preference_identifier: PreferenceIdentifier = "confirmBackToDashboard"
    value: bool = True


class ConfirmationDeleteStudyFrontendUserPreference(FrontendUserPreference):
    preference_identifier: PreferenceIdentifier = "confirmDeleteStudy"
    value: bool = True


class ConfirmationDeleteNodeFrontendUserPreference(FrontendUserPreference):
    preference_identifier: PreferenceIdentifier = "confirmDeleteNode"
    value: bool = True


class ConfirmationStopNodeFrontendUserPreference(FrontendUserPreference):
    preference_identifier: PreferenceIdentifier = "confirmStopNode"
    value: bool = True


class SnapNodeToGridFrontendUserPreference(FrontendUserPreference):
    preference_identifier: PreferenceIdentifier = "snapNodeToGrid"
    value: bool = True


class ConnectPortsAutomaticallyFrontendUserPreference(FrontendUserPreference):
    preference_identifier: PreferenceIdentifier = "autoConnectPorts"
    value: bool = True


class DoNotShowAnnouncementsFrontendUserPreference(FrontendUserPreference):
    preference_identifier: PreferenceIdentifier = "dontShowAnnouncements"
    value: list = Field(default_factory=list)


class ServicesFrontendUserPreference(FrontendUserPreference):
    preference_identifier: PreferenceIdentifier = "services"
    value: dict = Field(default_factory=dict)


class ThemeNameFrontendUserPreference(FrontendUserPreference):
    preference_identifier: PreferenceIdentifier = "themeName"
    value: str | None = None


class LastVcsRefUIFrontendUserPreference(FrontendUserPreference):
    preference_identifier: PreferenceIdentifier = "lastVcsRefUI"
    value: str | None = None


class PreferredWalletIdFrontendUserPreference(FrontendUserPreference):
    preference_identifier: PreferenceIdentifier = "preferredWalletId"
    value: int | None = None


class CreditsWarningThresholdFrontendUserPreference(FrontendUserPreference):
    preference_identifier: PreferenceIdentifier = "creditsWarningThreshold"
    value: int = 200


class WalletIndicatorVisibilityFrontendUserPreference(FrontendUserPreference):
    preference_identifier: PreferenceIdentifier = "walletIndicatorVisibility"
    value: str | None = "warning"


class UserInactivityThresholdFrontendUserPreference(FrontendUserPreference):
    preference_identifier: PreferenceIdentifier = "userInactivityThreshold"
    value: int = 30 * _MINUTE  # in seconds


class JobConcurrencyLimitFrontendUserPreference(FrontendUserPreference):
    preference_identifier: PreferenceIdentifier = "jobConcurrencyLimit"
    value: int | None = 1


class TelemetryLowDiskSpaceWarningThresholdFrontendUserPreference(
    FrontendUserPreference
):
    preference_identifier: PreferenceIdentifier = "lowDiskSpaceThreshold"
    value: int = 5  # in gigabytes


class TwoFAFrontendUserPreference(FrontendUserPreference):
    preference_identifier: PreferenceIdentifier = "twoFAPreference"
    value: TwoFactorAuthentificationMethod = TwoFactorAuthentificationMethod.SMS


class BillingCenterUsageColumnOrderFrontendUserPreference(FrontendUserPreference):
    preference_identifier: PreferenceIdentifier = "billingCenterUsageColumnOrder"
    value: list[int] | None = None


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
    p.get_preference_name(): p.model_fields["preference_identifier"].default
    for p in ALL_FRONTEND_PREFERENCES
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

    search_map: dict[str, type[FrontendUserPreference]] = {
        x.__name__: x for x in ALL_FRONTEND_PREFERENCES
    }

    for (
        preference_class,
        value,
    ) in settings.USERS_FRONTEND_PREFERENCES_DEFAULTS_OVERWRITES.items():
        search_map[preference_class].update_preference_default_value(value)
