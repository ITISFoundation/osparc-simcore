from pydantic.v1.errors import PydanticErrorMixin


class BaseDynamicSchedulerError(PydanticErrorMixin, ValueError):
    code = "simcore.service.dynamic.scheduler"
