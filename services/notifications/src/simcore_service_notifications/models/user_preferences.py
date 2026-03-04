from models_library.user_preferences import NotificationsUserPreference


class NotificationsGlobalSubscriptionPreference(NotificationsUserPreference):
    value: bool = True


class NotificationsEmailSubscriptionPreference(NotificationsUserPreference):
    value: bool = True
