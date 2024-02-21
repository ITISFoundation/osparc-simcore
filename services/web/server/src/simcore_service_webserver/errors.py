from models_library.errors_classes import OsparcErrorMixin


class WebServerBaseError(OsparcErrorMixin, Exception):
    ...
