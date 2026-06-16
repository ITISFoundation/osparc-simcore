"""Domain models for user_preferences."""

from models_library.shared_user_preferences import (
    AllowMetricsCollectionFrontendUserPreference,
)

from ._models import (
    ALL_FRONTEND_PREFERENCES,
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
    get_preference_identifier,
    get_preference_name,
    overwrite_user_preferences_defaults,
)

__all__: tuple[str, ...] = (
    # constants
    "ALL_FRONTEND_PREFERENCES",
    # models
    "AllowMetricsCollectionFrontendUserPreference",
    "BillingCenterUsageColumnOrderFrontendUserPreference",
    "ConfirmationBackToDashboardFrontendUserPreference",
    "ConfirmationDeleteNodeFrontendUserPreference",
    "ConfirmationDeleteStudyFrontendUserPreference",
    "ConfirmationStopNodeFrontendUserPreference",
    "ConnectPortsAutomaticallyFrontendUserPreference",
    "CreditsWarningThresholdFrontendUserPreference",
    "DoNotShowAnnouncementsFrontendUserPreference",
    "JobConcurrencyLimitFrontendUserPreference",
    "LastVcsRefUIFrontendUserPreference",
    "PreferredWalletIdFrontendUserPreference",
    "ServicesFrontendUserPreference",
    "SnapNodeToGridFrontendUserPreference",
    "TelemetryLowDiskSpaceWarningThresholdFrontendUserPreference",
    "ThemeNameFrontendUserPreference",
    "TwoFAFrontendUserPreference",
    "UserInactivityThresholdFrontendUserPreference",
    "WalletIndicatorVisibilityFrontendUserPreference",
    # functions
    "get_preference_identifier",
    "get_preference_name",
    "overwrite_user_preferences_defaults",
)
