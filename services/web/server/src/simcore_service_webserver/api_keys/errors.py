from ..errors import WebServerBaseError


class ApiKeysValueError(WebServerBaseError, ValueError):
    ...


class ApiKeyNotFoundError(ApiKeysValueError):
    msg_template = "API key not found. {reason}"
