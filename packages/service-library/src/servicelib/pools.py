from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from contextlib import contextmanager

from aiohttp import web

from .application_keys import APP_SHARED_THREAD_POOL_KEY


def get_shared_thread_pool(app: web.Application) -> ThreadPoolExecutor:
    """Ensures unique pool in the application"""
    pool = app(APP_SHARED_THREAD_POOL_KEY)
    if pool is None:
        pool = ThreadPoolExecutor()  # pylint: disable=consider-using-with
        app[APP_SHARED_THREAD_POOL_KEY] = pool

    return pool


def persistent_thread_pool(app: web.Application):
    """Ensures a single shared process pool is presnet of application

    IMPORTANT: Use this function ONLY in cleanup context , i.e.
        app.cleanup_ctx.append(persistent_client_session)

    SEE https://docs.aiohttp.org/en/latest/client_advanced.html#aiohttp-persistent-session
    """
    pool = get_shared_thread_pool(app)

    try:
        yield
    finally:
        pool.shutdown(wait=False)


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
