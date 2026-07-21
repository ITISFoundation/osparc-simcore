from collections.abc import AsyncIterator

import pytest
from aiointercept import aiointercept

from .helpers.host import get_localhost_ip

# Type alias used across the test-suite for annotations.
AiointerceptMock = aiointercept

# WARNING: with `mock_external_urls=True` aiointercept patches the DNS resolver
# process-wide so every aiohttp request to a *hostname* is redirected to the mock
# server. Bare IPs (e.g. the aiohttp test server bound to `127.0.0.1`) are never
# intercepted. We still list the localhost hosts as passthrough defensively, in case
# a client resolves the local test server by name.
PASSTHROUGH_REQUESTS_PREFIXES = [
    "127.0.0.1",
    "localhost",
    get_localhost_ip(),
]


@pytest.fixture
async def aiointercept_mocker() -> AsyncIterator[AiointerceptMock]:
    """Generic aiointercept mock

    SEE https://aiointercept.readthedocs.io

    Usage

        async def test_this(aiointercept_mocker):
            aiointercept_mocker.get("https://foo.io")

            async with aiohttp.ClientSession() as session:
                async with session.get("https://foo.io") as response:
                    assert response.status == 200
    """
    async with aiointercept(mock_external_urls=True, passthrough=PASSTHROUGH_REQUESTS_PREFIXES) as mock:
        yield mock
