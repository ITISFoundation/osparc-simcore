from pydantic.errors import PydanticErrorMixin


class AutoscalingRuntimeError(PydanticErrorMixin, RuntimeError):
    msg_template: str = "Autoscaling unexpected error"


class ConfigurationError(AutoscalingRuntimeError):
    msg_template: str = "Application misconfiguration: {msg}"


class Ec2NotConnectedError(AutoscalingRuntimeError):
    msg_template: str = "Cannot connect with ec2 server"


class Ec2InstanceNotFoundError(AutoscalingRuntimeError):
    msg_template: str = "EC2 instance was not found"


class Ec2TooManyInstancesError(AutoscalingRuntimeError):
    msg_template: str = (
        "The maximum amount of instances {num_instances} is already reached!"
    )


class Ec2InvalidDnsNameError(AutoscalingRuntimeError):
    msg_template: str = "Invalid EC2 private DNS name {aws_private_dns_name}"


class DaskSchedulerNotFoundError(AutoscalingRuntimeError):
    msg_template: str = "Scheduler in {url} was not found!"


class DaskWorkerNotFoundError(AutoscalingRuntimeError):
    msg_template: str = "Dask worker in {url} was not found!"
