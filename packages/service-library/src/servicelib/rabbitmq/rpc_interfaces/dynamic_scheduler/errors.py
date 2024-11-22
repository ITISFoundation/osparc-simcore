from common_library.errors_classes import OsparcErrorMixin


class BaseDynamicSchedulerRPCError(OsparcErrorMixin, Exception):
    ...


class ServiceWaitingForManualInterventionError(BaseDynamicSchedulerRPCError):
    msg_template = "Service {node_id} waiting for manual intervention"


class ServiceWasNotFoundError(BaseDynamicSchedulerRPCError):
    msg_template = "Service {node_id} was not found"
