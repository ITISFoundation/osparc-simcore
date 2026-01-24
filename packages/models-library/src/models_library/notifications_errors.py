from common_library.errors_classes import OsparcErrorMixin


class BaseNotificationsError(OsparcErrorMixin, Exception):
    """Base class for notification-related errors."""


class NotificationsTemplateNotFoundError(BaseNotificationsError):
    msg_template = "Notifications Template '{template_name}' for channel '{channel}' not found."
