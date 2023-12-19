from pydantic.errors import PydanticErrorMixin


class BaseDynamicSchedulerRPCError(Exception, PydanticErrorMixin):
    ...


class ServiceWaitingForManualInterventionError(BaseDynamicSchedulerRPCError):
    msg = "service waiting for manual intervention"


class ServiceWasNotFoundError(BaseDynamicSchedulerRPCError):
    msg = "service waiting for manual intervention"
