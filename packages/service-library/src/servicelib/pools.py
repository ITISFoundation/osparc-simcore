from collections.abc import Iterator
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from contextlib import contextmanager

# only gets created on use and is guaranteed to be the s
# ame for the entire lifetime of the application
__shared_process_pool_executor: dict[str, ProcessPoolExecutor] = {}
__shared_thread_pool_executor: dict[str, ThreadPoolExecutor] = {}


def _get_shared_process_pool_executor(**kwargs) -> ProcessPoolExecutor:
    # sometimes a pool requires a specific configuration
    # the key helps to distinguish between them in the same application
    key = "".join(sorted("_".join((k, str(v))) for k, v in kwargs.items()))

    if key not in __shared_process_pool_executor:
        # pylint: disable=consider-using-with
        __shared_process_pool_executor[key] = ProcessPoolExecutor(**kwargs)

    return __shared_process_pool_executor[key]


def _get_shared_thread_pool_executor(**kwargs) -> ThreadPoolExecutor:
    # sometimes a pool requires a specific configuration
    # the key helps to distinguish between them in the same application
    key = "".join(sorted("_".join((k, str(v))) for k, v in kwargs.items()))

    if key not in __shared_thread_pool_executor:
        # pylint: disable=consider-using-with
        __shared_thread_pool_executor[key] = ThreadPoolExecutor(**kwargs)

    return __shared_thread_pool_executor[key]


@contextmanager
def non_blocking_process_pool_executor(**kwargs) -> Iterator[ProcessPoolExecutor]:
    """
    Avoids default context manger behavior which calls
    shutdown with wait=True an blocks.
    """
    executor = _get_shared_process_pool_executor(**kwargs)
    try:
        yield executor
    finally:
        # NOTE: https://github.com/ITISFoundation/osparc-simcore/issues/3829
        # executor.shutdown(wait=False)
        pass


@contextmanager
def non_blocking_thread_pool_executor(**kwargs) -> Iterator[ThreadPoolExecutor]:
    """
    Avoids default context manger behavior which calls
    shutdown with wait=True an blocks.
    """
    executor = _get_shared_thread_pool_executor(**kwargs)
    try:
        yield executor
    finally:
        # NOTE: https://github.com/ITISFoundation/osparc-simcore/issues/3829
        # executor.shutdown(wait=False)
        pass
