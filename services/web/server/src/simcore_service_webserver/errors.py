from common_library.errors_classes import OsparcErrorMixin


class WebServerBaseError(OsparcErrorMixin, Exception):
    """WebServer base error."""
