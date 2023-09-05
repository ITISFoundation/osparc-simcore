from pydantic.errors import PydanticErrorMixin


class ClustersKeeperRuntimeError(PydanticErrorMixin, RuntimeError):
    msg_template: str = "clusters-keeper unexpected error"


class ConfigurationError(ClustersKeeperRuntimeError):
    msg_template: str = "Application misconfiguration: {msg}"


class Ec2NotConnectedError(ClustersKeeperRuntimeError):
    msg_template: str = "Cannot connect with ec2 server"


class Ec2InstanceNotFoundError(ClustersKeeperRuntimeError):
    msg_template: str = "EC2 instance was not found"


class Ec2TooManyInstancesError(ClustersKeeperRuntimeError):
    msg_template: str = (
        "The maximum amount of instances {num_instances} is already reached!"
    )
