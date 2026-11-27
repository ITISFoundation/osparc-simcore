from typing import Annotated, Any, ClassVar, Final

from common_library.basic_types import DEFAULT_FACTORY
from pydantic import EmailStr, Field, PositiveInt

from .authentication import TwoFactorAuthenticationMethod
from .user_preferences import FrontendUserPreference, PreferenceIdentifier

_MINUTE: Final[int] = 60
_HOUR: Final[int] = 60 * _MINUTE


class AllowMetricsCollectionFrontendUserPreference(FrontendUserPreference):
    preference_identifier: PreferenceIdentifier = "allowMetricsCollection"
    value: bool = True


class InvoiceEmailRecipientsFrontendUserPreference(FrontendUserPreference):
    preference_identifier: PreferenceIdentifier = "invoiceEmailRecipients"
    value: Annotated[list[EmailStr], Field(default_factory=list)] = DEFAULT_FACTORY


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
    value: Annotated[list, Field(default_factory=list)] = DEFAULT_FACTORY


class ServicesFrontendUserPreference(FrontendUserPreference):
    preference_identifier: PreferenceIdentifier = "services"
    value: Annotated[dict, Field(default_factory=dict)] = DEFAULT_FACTORY


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


class DefaultStudyTagIdsFrontendUserPreference(FrontendUserPreference):
    preference_identifier: PreferenceIdentifier = "defaultStudyTagIds"
    value: Annotated[list[PositiveInt], Field(default_factory=list)] = DEFAULT_FACTORY
