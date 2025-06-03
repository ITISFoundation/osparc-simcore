"""Dask task exceptions"""

from common_library.errors_classes import OsparcErrorMixin


class TaskValueError(OsparcErrorMixin, ValueError): ...


class TaskCancelledError(OsparcErrorMixin, RuntimeError):
    msg_template = "The task was cancelled"


class ServiceRuntimeError(OsparcErrorMixin, RuntimeError):
    msg_template = (
        "The service {service_key}:{service_version}"
        " running in container {container_id} failed with code"
        " {exit_code}. Last logs:\n{service_logs}"
    )


class ServiceInputsUseFileToKeyMapButReceivesZipDataError(
    OsparcErrorMixin, RuntimeError
):
    msg_template = (
        "The service {service_key}:{service_version} {input} uses a file-to-key {file_to_key_map} map but receives zip data instead. "
        "TIP: either pass a single file or zip file and remove the file-to-key map parameter."
    )
