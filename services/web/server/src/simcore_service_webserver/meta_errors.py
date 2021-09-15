""" meta exceptions

"""
from pydantic.errors import PydanticErrorMixin


class BaseMetaValueError(PydanticErrorMixin, ValueError):
    pass


class BaseMetaRuntimeError(PydanticErrorMixin, RuntimeError):
    pass


class NotFoundError(BaseMetaValueError):
    msg_template = "Could not find {name} '{value}'"


class InvalidParameterError(BaseMetaValueError):
    msg_template = "invalid {name}: {reason}"


class NoCommitError(BaseMetaRuntimeError):
    msg_template = "No commit found: {details}"


class CleanRequiredError(BaseMetaRuntimeError):
    msg_template = "working copy w/o changes (clean) is required: {details}"
