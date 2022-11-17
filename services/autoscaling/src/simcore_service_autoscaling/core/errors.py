from pydantic.errors import PydanticErrorMixin


class AutoscalingRuntimeError(PydanticErrorMixin, RuntimeError):
    ...


class Ec2InstanceNotFoundError(AutoscalingRuntimeError):
    code = "autoscaling.ec2_instance_not_found_error"
    msg_template: str = "Needed instance was not found"
