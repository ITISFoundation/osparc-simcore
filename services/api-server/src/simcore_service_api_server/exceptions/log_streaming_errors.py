from ._base import ApiServerBaseError


class LogStreamingBaseError(ApiServerBaseError):
    pass


class LogStreamerNotRegisteredError(LogStreamingBaseError):
    msg_template = "{msg}"


class LogStreamerRegistrationConflictError(LogStreamingBaseError):
    msg_template = "A stream was already connected to {job_id}. Only a single stream can be connected at the time"
