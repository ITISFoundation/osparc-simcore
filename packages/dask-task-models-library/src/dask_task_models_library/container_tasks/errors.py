""" Dask task exceptions

"""
from pydantic.errors import PydanticErrorMixin


class TaskValueError(PydanticErrorMixin, ValueError):
    pass


class ServiceRuntimeError(PydanticErrorMixin, RuntimeError):
    code = "service_runtime_error"
    msg_template = (
        "The service {service_key}:{service_version}"
        " in container {container_id} failed with code"
        " {exit_code}. Last logs:\n{service_logs}"
    )
