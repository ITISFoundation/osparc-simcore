from contextlib import contextmanager
from concurrent.futures import ProcessPoolExecutor


# because there is no shared fastapi library, this is a
# duplicate of servicelib.pools.non_blocking_process_pool_executor
@contextmanager
def non_blocking_process_pool_executor(**kwargs) -> ProcessPoolExecutor:
    """
    Avoids default context manger behavior which calls
    shutdown with wait=True an blocks.
    """
    pool = ProcessPoolExecutor(**kwargs)  # pylint: disable=consider-using-with
    try:
        yield pool
    finally:
        pool.shutdown(wait=False)
