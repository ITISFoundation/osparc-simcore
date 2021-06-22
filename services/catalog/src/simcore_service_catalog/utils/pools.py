from contextlib import contextmanager
from concurrent.futures import ProcessPoolExecutor


@contextmanager
def non_blocking_process_pool_executor(**kwargs) -> ProcessPoolExecutor:
    """
    Avoids default context manger behavior which calls
    shutdown with wait=True an blocks.
    """
    pool = ProcessPoolExecutor(**kwargs)  # pylint: disable=consider-using-with
    yield pool
    pool.shutdown(wait=False)
