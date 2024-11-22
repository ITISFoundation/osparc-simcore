from common_library.errors_classes import OsparcErrorMixin


class NotifierError(OsparcErrorMixin, Exception):
    pass


class TemplatesNotFoundError(NotifierError):
    msg_template = "Could not find {templates}"
