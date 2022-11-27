from pydantic.errors import PydanticErrorMixin


class AutoscalingRuntimeError(PydanticErrorMixin, RuntimeError):
    ...


class AutoscalingConfigurationError(AutoscalingRuntimeError):
    code = "autoscaling.configuration_error"
    msg_template: str = "Application misconfiguration: {msg}"


class Ec2InstanceNotFoundError(AutoscalingRuntimeError):
    code = "autoscaling.ec2_instance_not_found_error"
    msg_template: str = "Needed instance was not found"


class Ec2TooManyInstancesError(AutoscalingRuntimeError):
    code = "autoscaling.ec2_too_many_instances_error"
    msg_template: str = (
        "The maximum amount of instances {num_instances} is already reached!"
    )
