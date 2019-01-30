import tenacity
from yarl import URL
from aiohttp import ClientSession

import logging

logger = logging.getLogger(__name__)


RETRY_WAIT_SECS = 2
RETRY_COUNT = 20
CONNECT_TIMEOUT_SECS = 30


@tenacity.retry(
    wait=tenacity.wait_fixed(RETRY_WAIT_SECS),
    stop=tenacity.stop_after_attempt(RETRY_COUNT),
    before_sleep=tenacity.before_sleep_log(logger, logging.INFO),)
async def check_endpoint(url: URL, expected_response:int =200):
    """ Tenace check to GET given url endpoint

    Typically used to check connectivity to a given service

    In sync code use as
        loop.run_until_complete( check_endpoint(url) )

    :param url: endpoint service URL
    :type url: URL
    :param expected_response: expected http status, defaults to 200 (OK)
    :param expected_response: int, optional
    """
    async with ClientSession() as session:
        async with session.get(url) as resp:
            assert resp.status == expected_response

def is_url(location):
    return bool(URL(str(location)).host)
