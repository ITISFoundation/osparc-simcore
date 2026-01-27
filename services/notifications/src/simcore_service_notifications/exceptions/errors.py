from common_library.errors_classes import OsparcErrorMixin


class NotificationsRuntimeError(OsparcErrorMixin, RuntimeError): ...


class ContentModelNotFoundError(NotificationsRuntimeError):
    msg_template = "Content model for channel '{channel}' not found."
