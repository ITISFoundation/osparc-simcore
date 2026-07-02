import inspect
from collections.abc import Iterator
from unittest.mock import Mock

import aiohttp
import pytest
from aioresponses import aioresponses as AioResponsesMock  # noqa: N812

from .helpers.host import get_localhost_ip

# NOTE: WORKAROUND: aioresponses (<=0.7.9) builds `ClientResponse` without the
# `stream_writer` keyword-only argument that became REQUIRED in aiohttp 3.14.
# This raises `TypeError: ClientResponse.__init__() missing 1 required
# keyword-only argument: 'stream_writer'` when mocking requests.
# Patch `ClientResponse.__init__` to inject a default `stream_writer` when the
# caller (aioresponses) does not provide one. It is idempotent and a no-op on
# aiohttp versions where `stream_writer` is not part of the signature.
# SEE https://github.com/pnuckowski/aioresponses/issues/289
if "stream_writer" in inspect.signature(aiohttp.ClientResponse.__init__).parameters and not getattr(
    aiohttp.ClientResponse.__init__, "osparc_stream_writer_patched", False
):
    _original_client_response_init = aiohttp.ClientResponse.__init__

    def _patched_client_response_init(self, *args, **kwargs):
        kwargs.setdefault("stream_writer", Mock(output_size=0))
        _original_client_response_init(self, *args, **kwargs)

    _patched_client_response_init.osparc_stream_writer_patched = True  # type: ignore[attr-defined]
    aiohttp.ClientResponse.__init__ = _patched_client_response_init  # type: ignore[method-assign]

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
