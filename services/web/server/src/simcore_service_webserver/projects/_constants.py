from typing import Final

from common_library.user_messages import user_message

MSG_PARENT_NODE_NOT_FOUND_ERROR: Final[str] = user_message("Parent node '{node_uuid}' was not found.", _version=1)

MSG_PARENT_PROJECT_NOT_FOUND_ERROR: Final[str] = user_message(
    "The parent project you're looking for isn't available. Please check the reference and try again.",
    _version=1,
)

MSG_PROJECT_NOT_FOUND_ERROR: Final[str] = user_message("The project you're looking for could not be found.", _version=1)

MSG_INVALID_REQUEST_PARAMETER_ERROR: Final[str] = user_message(
    "The request contains invalid or missing parameters. Please check and try again.",
    _version=1,
)
