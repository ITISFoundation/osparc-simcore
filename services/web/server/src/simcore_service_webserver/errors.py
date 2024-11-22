from common_library.errors_classes import OsparcErrorMixin


class WebServerBaseError(OsparcErrorMixin, Exception):
    msg_template = "Error in web-server service"
