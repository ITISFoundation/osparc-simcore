from models_library.user_preferences import NotificationsUserPreference


class NotificationsSubscriptionEnabled(NotificationsUserPreference):
    value: bool = True


class NotificationsEmailSubscriptionEnabled(NotificationsUserPreference):
    value: bool = True
