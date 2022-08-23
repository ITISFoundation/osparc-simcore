from aiodocker.exceptions import DockerError
from models_library.projects_nodes import NodeID
from pydantic.errors import PydanticErrorMixin

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


class EntrypointContainerNotFoundError(DirectorException):
    """Raised while the entrypoint container was nto yet started"""


class LegacyServiceIsNotSupportedError(DirectorException):
    """This API is not implemented by the director-v0"""


class NodeportsDidNotFindNodeError(PydanticErrorMixin, DirectorException):
    code = "dynamic_scheduler.output_ports_pulling.node_not_found"
    msg_template = (
        "Could not find node '{node_uuid}' in the database. Did not upload data to S3, "
        "most likely due to service being removed from the study."
    )
