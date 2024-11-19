""" Dask task exceptions

"""
from common_library.errors_classes import OsparcErrorMixin


class TaskValueError(OsparcErrorMixin, ValueError):
    ...


class TaskCancelledError(OsparcErrorMixin, RuntimeError):
    msg_template = "The task was cancelled"


class ServiceRuntimeError(OsparcErrorMixin, RuntimeError):
    msg_template = (
        "The service {service_key}:{service_version}"
        " running in container {container_id} failed with code"
        " {exit_code}. Last logs:\n{service_logs}"
    )
