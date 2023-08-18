from typing import Any

from models_library.services import RunID
from pydantic.errors import PydanticErrorMixin


class BaseDynamicSidecarError(Exception):
    """Used as base for all exceptions"""

    def __init__(self, nessage: str, status: int = 500) -> None:
        self.message: str = nessage
        self.status: int = status
        super().__init__(nessage)


class VolumeNotFoundError(BaseDynamicSidecarError):
    def __init__(
        self, source_label: str, run_id: RunID, volumes: list[dict[str, Any]]
    ) -> None:
        super().__init__(
            f"Expected 1 got {len(volumes)} volumes labels with {source_label=}, {run_id=}: "
            f"Found {' '.join(v.get('Name', 'UNKNOWN') for v in volumes)}",
            status=404,
        )


class UnexpectedDockerError(BaseDynamicSidecarError):
    def __init__(self, message: str, status: int) -> None:
        super().__init__(
            f"An unexpected Docker error occurred {status=}, {message=}", status=status
        )


class BaseError(PydanticErrorMixin, BaseDynamicSidecarError):
    code = "dy_sidecar.error"


class ContainerExecContainerNotFoundError(BaseError):
    msg_template = "Could not find specified container {container_name}"


class ContainerExecTimeoutError(BaseError):
    msg_template = "Timed out after {timeout} while executing: {command}"
