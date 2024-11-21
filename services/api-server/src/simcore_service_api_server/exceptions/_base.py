from common_library.errors_classes import OsparcErrorMixin


class ApiServerBaseError(OsparcErrorMixin, Exception):
    ...
