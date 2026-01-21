from common_library.errors_classes import OsparcErrorMixin


class NotificationsRuntimeError(OsparcErrorMixin, RuntimeError): ...


class VariablesModelNotFoundError(NotificationsRuntimeError):
    msg_template = "Variables model for template '{template_ref}' not found"
