"""General purpose decorators

IMPORTANT: lowest level module
   I order to avoid cyclic dependences, please
   DO NOT IMPORT ANYTHING from .
"""

import logging
from copy import deepcopy
from functools import wraps

_logger = logging.getLogger(__name__)


def safe_return(if_fails_return=False, catch=None, logger=None):  # noqa: FBT002
    # defaults
    if catch is None:
        catch = (RuntimeError,)
    if logger is None:
        logger = _logger

    def decorate(func):
        @wraps(func)
        def safe_func(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except catch as err:
                logger.info("%s failed:  %s", func.__name__, str(err))
            except Exception:  # pylint: disable=broad-except
                logger.info("%s failed unexpectedly", func.__name__, exc_info=True)
            return deepcopy(if_fails_return)  # avoid issues with default mutable

        return safe_func

    return decorate
