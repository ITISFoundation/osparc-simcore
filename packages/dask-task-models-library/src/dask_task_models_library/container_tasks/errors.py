"""Dask task exceptions"""

from common_library.errors_classes import OsparcErrorMixin


class ContainerTaskError(OsparcErrorMixin, RuntimeError):
    msg_template = (
        "The service {service_key}:{service_version}"
        " running in container {container_id} encountered an unexpected error: {error_message}."
    )


class ServiceRuntimeError(ContainerTaskError):
    code = "runtime"  # type: ignore[assignment]
    msg_template = (
        "The service {service_key}:{service_version} running in container {container_id} failed with code {exit_code}."
    )


class ServiceOutOfMemoryError(ServiceRuntimeError):
    code = "runtime.oom"
    msg_template = (
        "The service {service_key}:{service_version}"
        " running in container {container_id} ran out of memory and was terminated."
        " Current limits are {service_resources}."
    )


class ServiceTimeoutLoggingError(ServiceRuntimeError):
    code = "runtime.timeout"
    msg_template = (
        "The service {service_key}:{service_version}"
        " running in container {container_id} was silent/hanging for longer than {timeout_timedelta} "
        "and was terminated."
    )


class TaskCancelledError(ContainerTaskError):
    msg_template = "The task was cancelled"


class ServiceInputsUseFileToKeyMapButReceivesZipDataError(ContainerTaskError):
    msg_template = (
        "The service {service_key}:{service_version} {input} uses a file-to-key {file_to_key_map} "
        "map but receives zip data instead. "
        "TIP: either pass a single file or zip file and remove the file-to-key map parameter."
    )
