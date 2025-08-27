from common_library.user_messages import user_message

from ..errors import WebServerBaseError


class FunctionGroupAccessRightsNotFoundError(WebServerBaseError, RuntimeError):
    msg_template = user_message(
        "Group access rights could not be found for Function '{function_id}' in product '{product_name}'."
    )


class IncompatiblePatchModelError(WebServerBaseError, ValueError):
    msg_template = user_message(
        "Incompatible patch model for Function '{function_id}' in product '{product_name}'."
    )
