from common_library.errors_classes import OsparcErrorMixin


class AutoscalingRuntimeError(OsparcErrorMixin, RuntimeError):
    msg_template: str = "Autoscaling unexpected error"


class ConfigurationError(AutoscalingRuntimeError):
    msg_template: str = "Application misconfiguration: {msg}"


class TaskRequiresUnauthorizedEC2InstanceTypeError(AutoscalingRuntimeError):
    msg_template: str = (
        "Task {task} requires unauthorized {instance_type}. "
        "TIP: check task required instance type or allow the instance type in autoscaling service settings"
    )


class TaskRequirementsAboveRequiredEC2InstanceTypeError(AutoscalingRuntimeError):
    msg_template: str = (
        "Task {task} requires {instance_type} but requires {resources}. "
        "TIP: Ensure task resources requirements fit required instance type available resources."
    )


class TaskBestFittingInstanceNotFoundError(AutoscalingRuntimeError):
    msg_template: str = (
        "Task requires {resources} but no instance type fits the requirements. "
        "TIP: Ensure task resources requirements fit available instance types."
    )


class Ec2InvalidDnsNameError(AutoscalingRuntimeError):
    msg_template: str = "Invalid EC2 private DNS name {aws_private_dns_name}"


class DaskSchedulerNotFoundError(AutoscalingRuntimeError):
    msg_template: str = "Scheduler in {url} was not found!"


class DaskNoWorkersError(AutoscalingRuntimeError):
    msg_template: str = "There are no dask workers connected to scheduler in {url}"


class DaskWorkerNotFoundError(AutoscalingRuntimeError):
    msg_template: str = "Dask worker running on {worker_host} is not registered to scheduler in {url}, it is not found!"
