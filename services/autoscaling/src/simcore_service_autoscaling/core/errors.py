from pydantic.errors import PydanticErrorMixin


class AutoscalingRuntimeError(PydanticErrorMixin, RuntimeError):
    msg_template: str = "Autoscaling unexpected error"


class ConfigurationError(AutoscalingRuntimeError):
    msg_template: str = "Application misconfiguration: {msg}"


class Ec2NotConnectedError(AutoscalingRuntimeError):
    msg_template: str = "Cannot connect with ec2 server"


class Ec2InstanceNotFoundError(AutoscalingRuntimeError):
    msg_template: str = "Needed instance was not found"


class Ec2TooManyInstancesError(AutoscalingRuntimeError):
    msg_template: str = (
        "The maximum amount of instances {num_instances} is already reached!"
    )
