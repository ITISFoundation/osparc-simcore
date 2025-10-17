from typing import Final

from .user_messages import user_message

MSG_TRY_AGAIN_OR_SUPPORT: Final[str] = user_message(
    "Please try again shortly. If the issue persists, contact support.", _version=1
)
