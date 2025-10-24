"""Dask task exceptions"""

from common_library.errors_classes import OsparcErrorMixin


class ContainerTaskError(OsparcErrorMixin, RuntimeError):
    msg_template = (
        "The service {service_key}:{service_version}"
        " running in container {container_id} encountered an unexpected error: {error_message}."
    )


class ServiceRuntimeError(ContainerTaskError):
    msg_template = (
        "The service {service_key}:{service_version}"
        " running in container {container_id} failed with code"
        " {exit_code}. Last logs:\n{service_logs}"
    )


class ServiceTimeoutLoggingError(ContainerTaskError):
    msg_template = (
        "The service {service_key}:{service_version}"
        " running in container {container_id} was detected as hanging and forcefully terminated by the platform. "
        "This happened because it exceeded the maximum allowed time of {timeout_timedelta} without producing any logs."
    )


class TaskCancelledError(ContainerTaskError):
    msg_template = "The task was cancelled"


class ServiceInputsUseFileToKeyMapButReceivesZipDataError(ContainerTaskError):
    msg_template = (
        "The service {service_key}:{service_version} {input} uses a file-to-key {file_to_key_map} map but receives zip data instead. "
        "TIP: either pass a single file or zip file and remove the file-to-key map parameter."
    )
