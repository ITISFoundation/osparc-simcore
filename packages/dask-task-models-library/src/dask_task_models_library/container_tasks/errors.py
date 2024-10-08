""" Dask task exceptions

"""
from common_library.errors_classes import OsparcErrorMixin


class TaskValueError(OsparcErrorMixin, ValueError):
    code = "task.value_error"  # type: ignore[assignment]


class TaskCancelledError(OsparcErrorMixin, RuntimeError):
    code = "task.cancelled_error"  # type: ignore[assignment]
    msg_template = "The task was cancelled"


class ServiceRuntimeError(OsparcErrorMixin, RuntimeError):
    code = "service.runtime_error"  # type: ignore[assignment]
    msg_template = (
        "The service {service_key}:{service_version}"
        " running in container {container_id} failed with code"
        " {exit_code}. Last logs:\n{service_logs}"
    )
