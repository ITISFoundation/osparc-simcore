from .base_exceptions import ApiServerBaseError


class LogDistributionBaseError(ApiServerBaseError):
    pass


class LogStreamerNotRegisteredError(LogDistributionBaseError):
    pass


class LogStreamerRegistionConflictError(LogDistributionBaseError):
    pass
