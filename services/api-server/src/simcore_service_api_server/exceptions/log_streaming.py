from ._base import ApiServerBaseError


class LogStreamingBaseError(ApiServerBaseError):
    pass


class LogStreamerNotRegisteredError(LogStreamingBaseError):
    pass


class LogStreamerRegistionConflictError(LogStreamingBaseError):
    pass
