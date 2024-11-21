# pylint: disable=too-many-ancestors
from common_library.errors_classes import OsparcErrorMixin


class EC2BaseError(OsparcErrorMixin, Exception):
    pass


class EC2RuntimeError(EC2BaseError, RuntimeError):
    msg_template: str = "EC2 client unexpected error"


class EC2NotConnectedError(EC2RuntimeError):
    msg_template: str = "Cannot connect with EC2 server"


class EC2AccessError(EC2RuntimeError):
    msg_template: str = (
        "Unexpected error while accessing EC2 backend: {operation_name}:{code}:{error}"
    )


class EC2TimeoutError(EC2AccessError):
    msg_template: str = "Timeout while accessing EC2 backend: {details}"


class EC2InstanceNotFoundError(EC2AccessError):
    msg_template: str = "EC2 instance was not found"


class EC2InstanceTypeInvalidError(EC2AccessError):
    msg_template: str = "EC2 instance type invalid"


class EC2TooManyInstancesError(EC2AccessError):
    msg_template: str = (
        "The maximum amount of instances {num_instances} is already reached!"
    )
