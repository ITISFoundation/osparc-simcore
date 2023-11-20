from pydantic.errors import PydanticErrorMixin


class EC2RuntimeError(PydanticErrorMixin, RuntimeError):
    msg_template: str = "EC2 client unexpected error"


class EC2InstanceNotFoundError(EC2RuntimeError):
    msg_template: str = "EC2 instance was not found"


class EC2InstanceTypeInvalidError(EC2RuntimeError):
    msg_template: str = "EC2 instance type invalid"


class EC2TooManyInstancesError(EC2RuntimeError):
    msg_template: str = (
        "The maximum amount of instances {num_instances} is already reached!"
    )
