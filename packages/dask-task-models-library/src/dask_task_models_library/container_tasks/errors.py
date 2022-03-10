""" Dask task exceptions

"""
from pydantic.errors import PydanticErrorMixin


class TaskValueError(PydanticErrorMixin, ValueError):
    code = "task.value_error"


class TaskCancelledError(PydanticErrorMixin, RuntimeError):
    code = "task.cancelled_error"
    msg_template = "The task was cancelled"


class ServiceRuntimeError(PydanticErrorMixin, RuntimeError):
    code = "service.runtime_error"
    msg_template = (
        "The service {service_key}:{service_version}"
        " in container {container_id} failed with code"
        " {exit_code}. Last logs:\n{service_logs}"
    )
