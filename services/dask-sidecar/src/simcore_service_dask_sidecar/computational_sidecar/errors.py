from ..errors import ComputationalSidecarRuntimeError


class ServiceBadFormattedOutputError(ComputationalSidecarRuntimeError):
    msg_template = "The service {service_key}:{service_version} produced badly formatted data: {exc}"
