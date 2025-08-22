from ..errors import WebServerBaseError


class ApiKeysValueError(WebServerBaseError, ValueError): ...


class ApiKeyDuplicatedDisplayNameError(ApiKeysValueError):
    msg_template = (
        "API Key with display name '{display_name}' already exists: {details}"
    )


class ApiKeyNotFoundError(ApiKeysValueError):
    msg_template = "API Key with ID '{api_key_id}' not found: {details}"
