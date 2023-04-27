from typing import Final

#
# NOTE: MSG_$(ERROR_CODE_NAME) strings MUST be human readable messages
#       Please keep alphabetical order
#

MSG_DATA_TOO_BIG: Final[str] = "File size {file_size_in_mb} MB is over allowed limit"

MSG_INCOMPATIBLE_SERVICE_AND_DATA: Final[
    str
] = "None of the registered viewers can open file type '{file_type}'"

MSG_INVALID_REDIRECTION_PARAMS_ERROR: Final[
    str
] = "Invalid request link: cannot find reference to either file or service"


MSG_PROJECT_NOT_FOUND: Final[str] = "Cannot find any study with ID '{project_id}'"


# This error happens when the linked study ID does not exists OR is not shared with everyone
MSG_PROJECT_NOT_PUBLISHED: Final[str] = "Cannot find any study with ID '{project_id}'"

# This error happens when the linked study ID does not exists OR is not shared with everyone OR is NOT public
MSG_PUBLIC_PROJECT_NOT_PUBLISHED: Final[str] = (
    "You need to be logged in to access study with ID '{project_id}'\n"
    "Please login and try again\n"
    "If you don't have an account, write to the Support email to request one\n"
)

MSG_GUESTS_NOT_ALLOWED: Final[str] = (
    "Access restricted to registered users\n"
    "If you don't have an account, write to the Support email to request one\n"
)

MSG_UNEXPECTED_ERROR: Final[
    str
] = "Opps this is embarrasing! Something went really wrong {hint}"
