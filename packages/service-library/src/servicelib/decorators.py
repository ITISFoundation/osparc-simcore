""" General purpose decorators

IMPORTANT: lowest level module
   I order to avoid cyclic dependences, please
   DO NOT IMPORT ANYTHING from .
"""
import logging
from copy import deepcopy
from functools import wraps

log = logging.getLogger(__name__)


def safe_return(if_fails_return=False, catch=None, logger=None):
    # defaults
    if catch is None:
        catch = (RuntimeError,)
    if logger is None:
        logger = log

    def decorate(func):
        @wraps(func)
        def safe_func(*args, **kargs):
            try:
                res = func(*args, **kargs)
                return res
            except catch as err:
                logger.info("%s failed:  %s", func.__name__, str(err))
            except Exception:  # pylint: disable=broad-except
                logger.info("%s failed unexpectedly", func.__name__, exc_info=True)
            return deepcopy(if_fails_return)  # avoid issues with default mutables

        return safe_func

    return decorate
