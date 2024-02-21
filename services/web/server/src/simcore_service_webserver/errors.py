from models_library.errors_classes import OsparcErrorMixin


class WebServerError(OsparcErrorMixin, Exception):
    ...
