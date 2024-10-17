from ..errors import WebServerBaseError


class SessionValueError(WebServerBaseError, ValueError):
    msg_template = "Invalid {invalid} in session"
