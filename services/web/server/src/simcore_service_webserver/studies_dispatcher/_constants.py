from typing import Final

# NOTE: MSG_$(ERROR_CODE_NAME) strings MUST be human readable messages


MSG_PROJECT_NOT_FOUND: Final[str] = "Cannot find any study with ID '{project_id}'"


MSG_PROJECT_NOT_PUBLISHED: Final[str] = "Cannot find any study with ID '{project_id}'"

MSG_PUBLIC_PROJECT_NOT_PUBLISHED: Final[
    str
] = "Cannot find any public study with ID '{project_id}'.\n Login and try again."


MSG_UNEXPECTED_ERROR: Final[
    str
] = "Opps this is embarrasing! Something went really wrong {hint}"
