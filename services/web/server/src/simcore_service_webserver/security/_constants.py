from typing import Final
from common_library.user_messages import user_message

MSG_UNAUTHORIZED: Final[str] = "Unauthorized"
MSG_AUTH_NOT_AVAILABLE: Final[str] = user_message(
    "Authentication service is temporary unavailable"
)

PERMISSION_PRODUCT_LOGIN_KEY: Final[str] = "product.login"
