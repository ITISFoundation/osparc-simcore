from typing import Final

from common_library.user_messages import user_message

#
# NOTE: MSG_$(ERROR_CODE_NAME) strings MUST be human readable messages
#       Please keep alphabetical order
#

MSG_PROJECT_NOT_FOUND: Final[str] = user_message(
    "The project with ID '{project_id}' could not be found.", _version=1
)

# This error happens when the linked project ID does not exists OR is not shared with everyone
MSG_PROJECT_NOT_PUBLISHED: Final[str] = user_message(
    "The project with ID '{project_id}' is not available or not shared.", _version=1
)

# This error happens when the linked project ID does not exists OR is not shared with everyone OR is NOT public
MSG_PUBLIC_PROJECT_NOT_PUBLISHED: Final[str] = user_message(
    "This project is only available for registered users.<br/><br/>"
    "Please log in and try again.<br/><br/>"
    "If you don't have an account, please request one at {support_email}.<br/><br/>",
    _version=1,
)

MSG_GUESTS_NOT_ALLOWED: Final[str] = user_message(
    "Access is restricted to registered users.<br/><br/>"
    "If you don't have an account, please contact support to request one.<br/><br/>",
    _version=1,
)

MSG_TOO_MANY_GUESTS: Final[str] = user_message(
    "We have reached the maximum number of anonymous users allowed on the platform. "
    "Please try again later or log in with a registered account.",
    _version=1,
)

MSG_UNEXPECTED_DISPATCH_ERROR: Final[str] = user_message(
    "Sorry, something unexpected went wrong! "
    "We track these errors automatically, but if the problem persists please contact us. "
    "In the meantime, try refreshing the page.",
    _version=1,
)
