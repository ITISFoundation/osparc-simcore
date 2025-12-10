from common_library.user_messages import user_message
from fastapi import status

from .backend_errors import BaseBackEndError


class BaseFunctionBackendError(BaseBackEndError):
    pass


class FunctionJobCacheNotFoundError(BaseBackEndError):
    msg_template: str = user_message("No cached function job was found.", _version=1)
    status_code: int = 404  # Not Found


class FunctionJobProjectMissingError(BaseBackEndError):
    msg_template: str = user_message("Unable to process the function job.", _version=1)
    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR  # Not Found
