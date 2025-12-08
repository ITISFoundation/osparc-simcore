from fastapi import status

from .backend_errors import BaseBackEndError


class BaseFunctionBackendError(BaseBackEndError):
    pass


class FunctionJobCacheNotFoundError(BaseBackEndError):
    msg_template: str = "No cached function job found."
    status_code: int = 404  # Not Found


class FunctionJobProjectMissingError(BaseBackEndError):
    msg_template: str = "Could not process function job"
    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR  # Not Found
