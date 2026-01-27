from ...core.errors import DirectorError


class DynamicSidecarError(DirectorError):
    msg_template: str = "Unexpected dynamic sidecar error: {msg}"


class DynamicSidecarNotFoundError(DirectorError):
    msg_template: str = "node {node_uuid} not found"


class DockerServiceNotFoundError(DirectorError):
    msg_template: str = "docker service with {service_id} not found"


class EntrypointContainerNotFoundError(DynamicSidecarError):
    """Raised while the entrypoint container was not yet started"""


class LegacyServiceIsNotSupportedError(DirectorError):
    """This API is not implemented by the director-v0"""


class UnexpectedContainerStatusError(DynamicSidecarError):
    msg_template: str = "Unexpected status from containers: {containers_with_error}"
