from common_library.errors_classes import OsparcErrorMixin


class BaseDynamicSidecarError(OsparcErrorMixin, Exception):
    """Used as base for all exceptions"""


class VolumeNotFoundError(BaseDynamicSidecarError):
    msg_template = (
        "Expected 1 got {volume_count} volumes labels with "
        "source_label={source_label}, run_id={run_id}: Found {volume_names}"
    )


class UnexpectedDockerError(BaseDynamicSidecarError):
    msg_template = "An unexpected Docker error occurred status_code={status_code}, message={message}"


class ContainerExecContainerNotFoundError(BaseDynamicSidecarError):
    msg_template = "Container '{container_name}' was not found"


class ContainerExecTimeoutError(BaseDynamicSidecarError):
    msg_template = "Timed out after {timeout} while executing: '{command}'"


class ContainerExecCommandFailedError(BaseDynamicSidecarError):
    msg_template = (
        "Command '{command}' exited with code '{exit_code}'"
        "and output: '{command_result}'"
    )
