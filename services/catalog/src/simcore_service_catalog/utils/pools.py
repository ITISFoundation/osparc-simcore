from contextlib import contextmanager
from concurrent.futures import ProcessPoolExecutor


@contextmanager
def non_blocking_process_pool_executor(**kwargs) -> ProcessPoolExecutor:
    """
    Avoids default context manger behavior which calls
    shutdown with wait=True an blocks.
    """
    pool = ProcessPoolExecutor(**kwargs)
    try:
        yield pool
    finally:
        pool.shutdown(wait=False)
