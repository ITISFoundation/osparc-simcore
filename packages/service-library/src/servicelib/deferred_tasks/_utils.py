import functools
import logging

from faststream.exceptions import HandlerException, RejectMessage

_logger = logging.getLogger(__name__)


def stop_retry_for_unintended_errors(func):
    """
    Stops FastStream's retry chain when an unexpected error is raised (bug or otherwise).
    This is especially important when the subscribers have ``retry=True``.

    Only propagate FastStream error that handle message acknowledgement.
    """

    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            if isinstance(e, HandlerException):
                raise

            msg = (
                "Error detected in user code. Aborting message retry. "
                f"Please check code at: '{func.__module__}.{func.__name__}'"
            )
            _logger.exception(msg)
            raise RejectMessage(msg) from e

    return wrapper
