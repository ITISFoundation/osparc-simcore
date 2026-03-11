from common_library.errors_classes import OsparcErrorMixin


class BaseNotificationsError(OsparcErrorMixin, Exception):
    """Base class for notification-related errors."""


class NotificationsTemplateNotFoundError(BaseNotificationsError):
    msg_template = "Template '{template_name}' not found for channel '{channel}'."


class NotificationsTemplateContextValidationError(BaseNotificationsError):
    msg_template = "Validation of context failed for template '{template_name}'."


class NotificationsUnsupportedChannelError(BaseNotificationsError):
    msg_template = "Channel '{channel}' is not supported."


class NotificationsNoActiveRecipientsError(BaseNotificationsError):
    msg_template = "No active recipients selected."
