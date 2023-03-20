from typing import Final

# NOTE: MSG_* strings MUST be human readable messages

MSG_PROJECT_NOT_FOUND: Final[str] = "Cannot find any study with ID '{project_id}'."


MSG_PROJECT_NOT_PUBLISHED: Final[
    str
] = "Cannot find any published study with ID '{project_id}'"


MSG_UNEXPECTED_ERROR: Final[
    str
] = "Opps this is embarrasing! Something went really wrong {hint}"
