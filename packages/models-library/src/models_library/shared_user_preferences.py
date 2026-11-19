from typing import Any, ClassVar, Final

from pydantic import EmailStr, Field

from .authentication import TwoFactorAuthenticationMethod
from .user_preferences import FrontendUserPreference, PreferenceIdentifier

_MINUTE: Final[int] = 60
_HOUR: Final[int] = 60 * _MINUTE


class AllowMetricsCollectionFrontendUserPreference(FrontendUserPreference):
    preference_identifier: PreferenceIdentifier = "allowMetricsCollection"
    value: bool = True


class InvoiceEmailRecipientsFrontendUserPreference(FrontendUserPreference):
    preference_identifier: PreferenceIdentifier = "invoiceEmailRecipients"
    value: list[EmailStr] = Field(default_factory=list)


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
    value_constraints: ClassVar[dict[str, Any]] = {"ge": 1 * _MINUTE, "le": 3 * _HOUR}


class JobConcurrencyLimitFrontendUserPreference(FrontendUserPreference):
    preference_identifier: PreferenceIdentifier = "jobConcurrencyLimit"
    value: int | None = 1


class TelemetryLowDiskSpaceWarningThresholdFrontendUserPreference(FrontendUserPreference):
    preference_identifier: PreferenceIdentifier = "lowDiskSpaceThreshold"
    value: int = 5  # in gigabytes


class TwoFAFrontendUserPreference(FrontendUserPreference):
    preference_identifier: PreferenceIdentifier = "twoFAPreference"
    value: TwoFactorAuthenticationMethod = TwoFactorAuthenticationMethod.SMS


class BillingCenterUsageColumnOrderFrontendUserPreference(FrontendUserPreference):
    preference_identifier: PreferenceIdentifier = "billingCenterUsageColumnOrder"
    value: list[int] | None = None
