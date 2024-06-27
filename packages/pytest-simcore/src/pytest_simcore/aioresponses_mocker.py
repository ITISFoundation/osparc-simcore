from collections.abc import Iterator

import pytest
from aioresponses import aioresponses as AioResponsesMock  # noqa: N812

from .helpers.host import get_localhost_ip

# WARNING: any request done through the client will go through aioresponses. It is
# unfortunate but that means any valid request (like calling the test server) prefix must be set as passthrough.
# Other than that it seems to behave nicely
PASSTHROUGH_REQUESTS_PREFIXES = [
    "http://127.0.0.1",
    "ws://",
    f"http://{get_localhost_ip()}",
]


@pytest.fixture
def aioresponses_mocker() -> Iterator[AioResponsesMock]:
    """Generick aioresponses mock

    SEE https://github.com/pnuckowski/aioresponses

    Usage

        async def test_this(aioresponses_mocker):
            aioresponses_mocker.get("https://foo.io")

            async with aiohttp.ClientSession() as session:
                async with session.get("https://foo.io") as response:
                    assert response.status == 200
    """
    with AioResponsesMock(passthrough=PASSTHROUGH_REQUESTS_PREFIXES) as mock:
        yield mock
