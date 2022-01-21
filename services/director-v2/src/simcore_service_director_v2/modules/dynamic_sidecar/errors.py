from typing import Optional

from aiodocker.exceptions import DockerError
from httpx import Response
from models_library.projects_nodes import NodeID

from ...core.errors import DirectorException


class DynamicSidecarError(DirectorException):
    pass


class GenericDockerError(DynamicSidecarError):
    """Generic docker library error"""

    def __init__(self, msg: str, original_exception: DockerError):
        super().__init__(msg + f": {original_exception.message}")
        self.original_exception = original_exception


class DynamicSidecarNotFoundError(DirectorException):
    """Dynamic sidecar was not found"""

    def __init__(self, node_uuid: NodeID):
        super().__init__(f"node {node_uuid} not found")


class DynamicSchedulerException(DirectorException):
    """
    Used to signal that something was wrong with during
    the service's observation.
    """


class EntrypointContainerNotFoundError(DirectorException):
    """Raised while the entrypoint container was nto yet started"""


class LegacyServiceIsNotSupportedError(DirectorException):
    """This API is not implemented by the director-v0"""


class DynamicSidecarUnexpectedResponseStatus(DirectorException):
    """Used to signal that there was an issue with a request"""

    def __init__(self, response: Response, msg: Optional[str] = None):
        formatted_tag = f"[during {msg}]" if msg is not None else ""
        message = (
            f"Unexpected response {formatted_tag}: status={response.status_code}, "
            f"body={response.text}"
        )
        super().__init__(message)
        self.response = response
