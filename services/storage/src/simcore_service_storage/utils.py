import logging

import tenacity
from aiohttp import ClientSession
from yarl import URL

logger = logging.getLogger(__name__)


RETRY_WAIT_SECS = 2
RETRY_COUNT = 20
CONNECT_TIMEOUT_SECS = 30


@tenacity.retry(
    wait=tenacity.wait_fixed(RETRY_WAIT_SECS),
    stop=tenacity.stop_after_attempt(RETRY_COUNT),
    before_sleep=tenacity.before_sleep_log(logger, logging.INFO),
)
async def assert_enpoint_is_ok(
    session: ClientSession, url: URL, expected_response: int = 200
):
    """ Tenace check to GET given url endpoint

    Typically used to check connectivity to a given service

    In sync code use as
        loop.run_until_complete( check_endpoint(url) )

    :param url: endpoint service URL
    :type url: URL
    :param expected_response: expected http status, defaults to 200 (OK)
    :param expected_response: int, optional
    """
    async with session.get(url) as resp:
        if resp.status != expected_response:
            raise AssertionError(f"{resp.status} != {expected_response}")


def is_url(location):
    return bool(URL(str(location)).host)


def expo(base=1.2, factor=0.1, max_value=2):
    """Generator for exponential decay.
    Args:
        base: The mathematical base of the exponentiation operation
        factor: Factor to multiply the exponentation by.
        max_value: The maximum value until it will yield
    """
    n = 0
    while True:
        a = factor * base ** n
        if max_value is None or a < max_value:
            yield a
            n += 1
        else:
            yield max_value