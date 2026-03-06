from common_library.errors_classes import OsparcErrorMixin


class _BaseError(OsparcErrorMixin, Exception):
    """Base class for notification-related errors."""


class TemplateNotFoundError(_BaseError):
    msg_template = "Template '{template_name}' not found for channel '{channel}'."


class TemplateContextValidationError(_BaseError):
    msg_template = "Validation of context failed for template '{template_name}'."


class UnsupportedChannelError(_BaseError):
    msg_template = "Channel '{channel}' is not supported."


class NoActiveContactsError(_BaseError):
    msg_template = "No active contacts selected."
