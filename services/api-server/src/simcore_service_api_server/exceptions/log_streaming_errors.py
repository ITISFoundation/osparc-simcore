from common_library.user_messages import user_message

from ._base import ApiServerBaseError


class LogStreamingBaseError(ApiServerBaseError):
    pass


class LogStreamerNotRegisteredError(LogStreamingBaseError):
    msg_template = "{msg}"


class LogStreamerRegistrationConflictError(LogStreamingBaseError):
    msg_template = user_message(
        "A stream is already connected to {job_id}. Only one stream can be connected at a time.",
        _version=1,
    )
