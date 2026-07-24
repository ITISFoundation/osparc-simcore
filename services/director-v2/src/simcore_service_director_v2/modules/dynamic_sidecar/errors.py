from typing import Any

from aiodocker import DockerError

from ...core.errors import DirectorError


class DynamicSidecarError(DirectorError):
    msg_template: str = "Unexpected dynamic sidecar error: {msg}"


class GenericDockerError(DynamicSidecarError):
    def __init__(self, original_exception: DockerError, **ctx: Any) -> None:
        super().__init__(original_exception=original_exception, **ctx)
        self.original_exception = original_exception

    msg_template: str = "Unexpected error using docker client: {msg}"


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


class InsufficientResourcesAfterProxyReservationError(DynamicSidecarError):
    msg_template: str = (
        "Not enough resources for service '{service_key}': subtracting the "
        "dynamic-sidecar-proxy reservation would bring '{resource_name}' "
        "{resource_field} to {new_value} (must remain > 0)"
    )
