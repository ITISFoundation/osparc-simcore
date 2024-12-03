from ..errors import WebServerBaseError


class ApiKeysValueError(WebServerBaseError, ValueError):
    ...


class ApiKeyNotFoundError(ApiKeysValueError):
    msg_template = "API Key with ID '{api_key_id}' not found. {reason}"
