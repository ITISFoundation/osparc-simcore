from pydantic.errors import PydanticErrorMixin


class ComputationalSidecarRuntimeError(PydanticErrorMixin, RuntimeError):
    ...


class ServiceRunError(ComputationalSidecarRuntimeError):
    msg_template = (
        "The service {service_key}:{service_version} running"
        "in container {container_id} failed with exit code {exit_code}\n"
        "last logs: {service_logs}"
    )


class ServiceBadFormattedOutputError(ComputationalSidecarRuntimeError):
    msg_template = "The service {service_key}:{service_version} produced badly formatted data: {exc}"
