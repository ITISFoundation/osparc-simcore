from collections.abc import Iterator

import aiohttp
import pytest
from aioresponses import aioresponses as AioResponsesMock  # noqa: N812
from pytest_mock import MockerFixture

from .helpers.aioresponses import (
    is_stream_writer_patch_needed,
    patched_client_response_init,
)
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
def aioresponses_mocker(mocker: MockerFixture) -> Iterator[AioResponsesMock]:
    """Generick aioresponses mock

    SEE https://github.com/pnuckowski/aioresponses

    Usage

        async def test_this(aioresponses_mocker):
            aioresponses_mocker.get("https://foo.io")

            async with aiohttp.ClientSession() as session:
                async with session.get("https://foo.io") as response:
                    assert response.status == 200
    """
    if is_stream_writer_patch_needed():
        mocker.patch.object(aiohttp.ClientResponse, "__init__", patched_client_response_init)

    with AioResponsesMock(passthrough=PASSTHROUGH_REQUESTS_PREFIXES) as mock:
        yield mock
