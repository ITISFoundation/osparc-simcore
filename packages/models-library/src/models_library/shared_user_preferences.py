from .user_preferences import FrontendUserPreference


class AllowMetricsCollectionFrontendUserPreference(FrontendUserPreference):
    preference_identifier = "allowMetricsCollection"
    value: bool = True
