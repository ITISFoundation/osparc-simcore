from pydantic.errors import PydanticErrorMixin


class BaseDynamicSchedulerRPCError(Exception, PydanticErrorMixin):
    ...


class ServiceWaitingForManualInterventionError(BaseDynamicSchedulerRPCError):
    msg = "Service {node_id} waiting for manual intervention"


class ServiceWasNotFoundError(BaseDynamicSchedulerRPCError):
    msg = "Service {node_id} was not found"
