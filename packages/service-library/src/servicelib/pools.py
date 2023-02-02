import asyncio
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from contextlib import contextmanager
from typing import Any, Callable, Iterator

# only gets created on use and is guaranteed to be the s
# ame for the entire lifetime of the application
__shared_process_pool_executor = {}


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

    if key not in __shared_process_pool_executor:
        # pylint: disable=consider-using-with
        __shared_process_pool_executor[key] = ThreadPoolExecutor(**kwargs)

    return __shared_process_pool_executor[key]


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
        # due to an issue in cpython https://bugs.python.org/issue34073
        # bypassing shutdown and using a shared pool
        # remove call to get_shared_process_pool_executor and replace with
        # a new instance when the issue is fixed
        # FIXME: uncomment below line when the issue is fixed
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
        executor.shutdown(wait=False)


async def async_on_threadpool(callable_function: Callable, *args: Any) -> Any:
    """Ensures blocking operation runs on shared thread pool"""
    return await asyncio.get_event_loop().run_in_executor(
        None, callable_function, *args
    )
