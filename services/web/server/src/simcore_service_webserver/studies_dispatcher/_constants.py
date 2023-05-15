from typing import Final

#
# NOTE: MSG_$(ERROR_CODE_NAME) strings MUST be human readable messages
#       Please keep alphabetical order
#

# product = get_current_product()

MSG_PROJECT_NOT_FOUND: Final[str] = "Cannot find any study with ID '{project_id}'"

# This error happens when the linked study ID does not exists OR is not shared with everyone
MSG_PROJECT_NOT_PUBLISHED: Final[str] = "Cannot find any study with ID '{project_id}'"

# This error happens when the linked study ID does not exists OR is not shared with everyone OR is NOT public
MSG_PUBLIC_PROJECT_NOT_PUBLISHED: Final[str] = (
    "Please login and try again.<br/><br/>"
    "If you don't have an account, please request one at {support_email}<br/><br/>"
)

MSG_GUESTS_NOT_ALLOWED: Final[str] = (
    "Access restricted to registered users.\n"
    "If you don't have an account, please email to support and request one\n"
)

MSG_UNEXPECTED_ERROR: Final[
    str
] = "Opps this is embarrasing! Something went really wrong {hint}"
