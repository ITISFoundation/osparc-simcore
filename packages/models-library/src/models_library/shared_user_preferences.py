from .user_preferences import FrontendUserPreference


class AllowMetricsCollectionFrontendUserPreference(FrontendUserPreference):
    preference_identifier: str = "allowMetricsCollection"
    value: bool = True
