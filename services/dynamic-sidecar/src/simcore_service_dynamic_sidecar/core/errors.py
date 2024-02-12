from typing import Any

from fastapi import status
from models_library.services import RunID
from pydantic.errors import PydanticErrorMixin


class BaseDynamicSidecarError(Exception):
    """Used as base for all exceptions"""

    def __init__(
        self, nessage: str, status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    ) -> None:
        self.message: str = nessage
        self.status_code: int = status_code
        super().__init__(nessage)


class VolumeNotFoundError(BaseDynamicSidecarError):
    def __init__(
        self, source_label: str, run_id: RunID, volumes: list[dict[str, Any]]
    ) -> None:
        super().__init__(
            f"Expected 1 got {len(volumes)} volumes labels with {source_label=}, {run_id=}: "
            f"Found {' '.join(v.get('Name', 'UNKNOWN') for v in volumes)}",
            status_code=status.HTTP_404_NOT_FOUND,
        )


class UnexpectedDockerError(BaseDynamicSidecarError):
    def __init__(self, message: str, status_code: int) -> None:
        super().__init__(
            f"An unexpected Docker error occurred {status_code=}, {message=}",
            status_code=status_code,
        )


class BaseError(PydanticErrorMixin, BaseDynamicSidecarError):
    code = "dy_sidecar.error"


class ContainerExecContainerNotFoundError(BaseError):
    msg_template = "Container '{container_name}' was not found"


class ContainerExecTimeoutError(BaseError):
    msg_template = "Timed out after {timeout} while executing: '{command}'"


class ContainerExecCommandFailedError(BaseError):
    msg_template = (
        "Command '{command}' exited with code '{exit_code}'"
        "and output: '{command_result}'"
    )
