from typing import Final

# NOTE: MSG_$(ERROR_CODE_NAME) strings MUST be human readable messages


MSG_PROJECT_NOT_FOUND: Final[str] = "Cannot find any study with ID '{project_id}'"


# This error happens when the linked study ID does not exists OR is not shared with everyone
MSG_PROJECT_NOT_PUBLISHED: Final[str] = "Cannot find any study with ID '{project_id}'"

# This error happens when the linked study ID does not exists OR is not shared with everyone OR is NOT public
MSG_PUBLIC_PROJECT_NOT_PUBLISHED: Final[str] = (
    "You need to be logged in to access study with ID '{project_id}'\n"
    "Please login and try again\n"
    "If you don't have an account, write to the Support email to request one\n"
)


MSG_UNEXPECTED_ERROR: Final[
    str
] = "Opps this is embarrasing! Something went really wrong {hint}"
