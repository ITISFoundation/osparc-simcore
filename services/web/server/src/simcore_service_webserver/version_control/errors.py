from ..errors import WebServerBaseError


class VersionControlValueError(WebServerBaseError, ValueError):
    pass


class VersionControlRuntimeError(WebServerBaseError, RuntimeError):
    pass


class NotFoundError(VersionControlValueError):
    msg_template = "Could not find {name} '{value}'"


class InvalidParameterError(VersionControlValueError):
    msg_template = "Invalid {name}: {reason}"


class NoCommitError(VersionControlRuntimeError):
    msg_template = "No commit found: {details}"


class CleanRequiredError(VersionControlRuntimeError):
    msg_template = "Working copy w/o changes (clean) is required: {details}"


class UserUndefinedError(VersionControlRuntimeError):
    msg_template = "User required but undefined"
