import inspect
import logging
import sys
from typing import Any, Callable, Dict, Tuple, Type, Union

from tenacity import RetryCallState, _utils
from tenacity.retry import retry_base

logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)
logger = logging.getLogger(__name__)


def _log_if_code_succeeds(retry_state: RetryCallState) -> None:
    message = (
        f"Execution succeeded for '{_utils.get_callback_name(retry_state.fn)}', "
        f"this is the {_utils.to_ordinal(retry_state.attempt_number)} time calling it."
    )
    logger.debug(message)


class retry_if_exception_type_and_log_success(retry_base):
    """
    Like default policy plus logging.
    Retries if an exception has been raised for one or more types.
    """

    def __init__(
        self,
        exception_types: Union[
            Type[BaseException],
            Tuple[Type[BaseException], ...],
        ] = Exception,
    ) -> None:
        self.predicate: Callable[[BaseException], bool] = lambda e: isinstance(
            e, exception_types
        )

    def __call__(self, retry_state: RetryCallState) -> bool:
        if retry_state.outcome.failed:
            return self.predicate(retry_state.outcome.exception())

        _log_if_code_succeeds(retry_state)
        return False


def _set_parameter(
    overwrite_retry_paramenter: bool, kwargs: Dict[str, Any], key: str, value: Any
) -> None:
    if key in kwargs:
        frame = inspect.stack()[2]
        file_name, line_number, function_name = frame[1], frame[2], frame[3]
        if overwrite_retry_paramenter:
            message = (
                f"Parementer '{key}={kwargs[key]}' set to '{value}' "
                f"at '{file_name}::{function_name}:{line_number}'"
            )

        else:
            message = (
                f"Parementer '{key}={kwargs[key]}' WILL NOT BE SET TO '{value}' "
                f"at '{file_name}::{function_name}:{line_number}'"
            )
        logging.warning(message)

        if overwrite_retry_paramenter:
            return

    kwargs[key] = value


def add_defaults(
    overwrite_retry_paramenter: bool = False, **kwargs: Any
) -> Dict[str, Any]:
    """Adds some extra parameters to make help with debugging"""
    _set_parameter(
        overwrite_retry_paramenter=overwrite_retry_paramenter,
        kwargs=kwargs,
        key="retry",
        value=retry_if_exception_type_and_log_success(),
    )
    # always reraise the original exception
    _set_parameter(
        overwrite_retry_paramenter=overwrite_retry_paramenter,
        kwargs=kwargs,
        key="reraise",
        value=True,
    )
    return kwargs
