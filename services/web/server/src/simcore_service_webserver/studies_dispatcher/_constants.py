from typing import Final

from common_library.user_messages import user_message

#
# NOTE: MSG_$(ERROR_CODE_NAME) strings MUST be human readable messages
#       Please keep alphabetical order
#

MSG_PROJECT_NOT_FOUND: Final[str] = user_message(
    "Cannot find any study with ID '{project_id}'"
)

# This error happens when the linked study ID does not exists OR is not shared with everyone
MSG_PROJECT_NOT_PUBLISHED: Final[str] = user_message(
    "Cannot find any study with ID '{project_id}'"
)

# This error happens when the linked study ID does not exists OR is not shared with everyone OR is NOT public
MSG_PUBLIC_PROJECT_NOT_PUBLISHED: Final[str] = user_message(
    "Only available for registered users.<br/><br/>"
    "Please login and try again.<br/><br/>"
    "If you don't have an account, please request one at {support_email}<br/><br/>"
)

MSG_GUESTS_NOT_ALLOWED: Final[str] = user_message(
    "Access restricted to registered users.<br/><br/>"
    "If you don't have an account, please email to support and request one<br/><br/>"
)

MSG_TOO_MANY_GUESTS: Final[str] = user_message(
    "We have reached the maximum of anonymous users allowed the platform. "
    "Please try later or login with a registered account."
)

MSG_UNEXPECTED_DISPATCH_ERROR: Final[str] = user_message(
    "Sorry, but looks like something unexpected went wrong!"
    "We track these errors automatically, but if the problem persists feel free to contact us."
    "In the meantime, try refreshing."
)
