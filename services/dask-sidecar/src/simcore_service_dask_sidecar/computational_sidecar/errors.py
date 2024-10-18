from common_library.errors_classes import OsparcErrorMixin


class ComputationalSidecarRuntimeError(OsparcErrorMixin, RuntimeError):
    ...


class ServiceBadFormattedOutputError(ComputationalSidecarRuntimeError):
    msg_template = "The service {service_key}:{service_version} produced badly formatted data: {exc}"
