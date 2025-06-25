from typing import Final

from common_library.user_messages import user_message

from ..constants import MSG_TRY_AGAIN_OR_SUPPORT

MSG_CATALOG_SERVICE_UNAVAILABLE: Final[str] = user_message(
    # Most likely the director service is down or misconfigured so the user is asked to try again later.
    "The catalog service is currently unavailable. This issue has been logged and will be investigated. "
    + MSG_TRY_AGAIN_OR_SUPPORT,
    _version=1,
)


MSG_CATALOG_SERVICE_NOT_FOUND: Final[str] = "Not Found"
