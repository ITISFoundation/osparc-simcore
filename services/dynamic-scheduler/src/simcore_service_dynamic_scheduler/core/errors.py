from pydantic.errors import PydanticErrorMixin


class BaseDynamicSchedulerError(PydanticErrorMixin, ValueError):
    code = "simcore.service.dynamic.scheduler"
