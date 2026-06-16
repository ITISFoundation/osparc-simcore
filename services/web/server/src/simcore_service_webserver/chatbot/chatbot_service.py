# mypy: disable-error-code=truthy-function
from ._client import get_chatbot_rest_client

__all__: tuple[str, ...] = (
    # functions
    "get_chatbot_rest_client",
)
