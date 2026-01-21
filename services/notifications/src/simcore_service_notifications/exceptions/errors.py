from common_library.errors_classes import OsparcErrorMixin


class NotificationsRuntimeError(OsparcErrorMixin, RuntimeError): ...


class ContentModelNotFoundError(NotificationsRuntimeError):
    msg_template = "Content model for channel '{channel}' not found"


class VariablesModelNotFoundError(NotificationsRuntimeError):
    msg_template = "Variables model for template '{template_ref}' not found"
