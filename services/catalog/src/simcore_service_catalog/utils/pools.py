from concurrent.futures import ProcessPoolExecutor
from contextlib import contextmanager

# only gets created on use and is guaranteed to be the s
# ame for the entire lifetime of the application
__shared_process_pool_executor = None


def get_shared_process_pool_executor(**kwargs) -> ProcessPoolExecutor:
    global __shared_process_pool_executor  # pylint: disable=global-statement

    if __shared_process_pool_executor is None:
        # pylint: disable=consider-using-with
        __shared_process_pool_executor = ProcessPoolExecutor(**kwargs)

    return __shared_process_pool_executor


# because there is no shared fastapi library, this is a
# duplicate of servicelib.pools.non_blocking_process_pool_executor
@contextmanager
def non_blocking_process_pool_executor(**kwargs) -> ProcessPoolExecutor:
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
        # executor.shutdown(wait=False)
        pass
