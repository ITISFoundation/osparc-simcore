from pydantic.errors import PydanticErrorMixin


class ComputationalSidecarRuntimeError(PydanticErrorMixin, RuntimeError): ...


class ServiceBadFormattedOutputError(ComputationalSidecarRuntimeError):
    msg_template = "The service {service_key}:{service_version} produced badly formatted data: {exc}"
