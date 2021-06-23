from concurrent.futures import ProcessPoolExecutor
from contextlib import contextmanager

# because
_shared_process_pool_executor = None


def get_shared_process_pool_executor(**kwargs) -> ProcessPoolExecutor:
    global _shared_process_pool_executor  # pylint: disable=global-statement

    if _shared_process_pool_executor is None:
        _shared_process_pool_executor = ProcessPoolExecutor(
            **kwargs
        )  # pylint: disable=consider-using-with

    return _shared_process_pool_executor


@contextmanager
def non_blocking_process_pool_executor(**kwargs) -> ProcessPoolExecutor:
    # ideally a shared
    """
    Avoids default context manger behavior which calls
    shutdown with wait=True an blocks.
    """
    executor = get_shared_process_pool_executor(**kwargs)
    try:
        yield executor
    finally:
        # due to an issue in cpython https://bugs.python.org/issue34073
        # bypassing shutdown and using a shared pool
        # remove call to get_shared_process_pool_executor and replace with
        # a new instance when the issue is fixed
        pass
