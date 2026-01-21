from common_library.errors_classes import OsparcErrorMixin


class VariablesModelNotFoundError(OsparcErrorMixin, Exception):
    msg_template = "Variables model for template '{template_ref}' not found."
