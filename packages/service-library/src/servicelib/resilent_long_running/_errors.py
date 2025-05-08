from common_library.errors_classes import OsparcErrorMixin


class BaseLongRunningError(OsparcErrorMixin, Exception):
    pass


class UnexpectedJobNotFoundError(BaseLongRunningError):
    msg_template = (
        "this could be a possible issue, expected to find an entry id={unique_id}"
    )


class FinishedWithError(BaseLongRunningError):
    msg_template = "unique_id='{unique_id}' finished with error='{error}' message='{message}'\n{traceback}"


class NoMoreRetryAttemptsError(FinishedWithError):
    msg_template = "attempt {remaining_attempts} of {retry_count} for unique_id='{unique_id}' with last_result='{last_result}'"


class UnexpectedStatusError(BaseLongRunningError):
    msg_template = (
        "status={status} could not find anything with unique_id='{unique_id}'"
    )


class AlreadyStartedError(BaseLongRunningError):
    msg_template = "unique_id='{unique_id}' is already running, skipped starting it"


class JobNotFoundError(BaseLongRunningError):
    msg_template = "unique_id='{unique_id}' is not present"


class NoResultIsAvailableError(BaseLongRunningError):
    msg_template = "unique_id='{unique_id}' has not finished"


class TimedOutError(BaseLongRunningError):
    msg_template = (
        "unique_id='{unique_id}' has not finished. Timedout after '{timeout}' "
        "on attempt {remaining_attempts}."
    )


class UnexpectedResultTypeError(BaseLongRunningError):
    msg_template = "result='{result}' has unexpcted type '{result_type}', was expecting '{expected_type}'"
