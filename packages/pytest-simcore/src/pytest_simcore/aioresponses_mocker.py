import inspect
import warnings
from collections.abc import Iterator
from unittest.mock import Mock

import aiohttp
import pytest
from aioresponses import aioresponses as AioResponsesMock  # noqa: N812
from pytest_mock import MockerFixture

from .helpers.host import get_localhost_ip

# WARNING: any request done through the client will go through aioresponses. It is
# unfortunate but that means any valid request (like calling the test server) prefix must be set as passthrough.
# Other than that it seems to behave nicely
PASSTHROUGH_REQUESTS_PREFIXES = [
    "http://127.0.0.1",
    "ws://",
    f"http://{get_localhost_ip()}",
]


_orig_client_response_init = aiohttp.ClientResponse.__init__


def _is_stream_writer_patch_needed() -> bool:
    return "stream_writer" in inspect.signature(_orig_client_response_init).parameters


def _patched_client_response_init(self, *args, **kwargs):
    # NOTE: aioresponses (<=0.7.9) builds `ClientResponse` without the
    # `stream_writer` keyword-only argument that became REQUIRED in aiohttp 3.14.
    # This raises `TypeError: ClientResponse.__init__() missing 1 required
    # keyword-only argument: 'stream_writer'` when mocking requests, therefore we
    # inject a default `stream_writer` when the caller (aioresponses) does not provide one.
    warnings.warn(
        "aioresponses is missing the `stream_writer` keyword-only argument"
        " required by aiohttp>=3.14, therefore `ClientResponse.__init__` is manually patched."
        " TIP: periodically check if it gets updated https://github.com/pnuckowski/aioresponses/issues/289",
        UserWarning,
        stacklevel=1,
    )
    kwargs.setdefault("stream_writer", Mock(output_size=0))
    _orig_client_response_init(self, *args, **kwargs)


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
    if _is_stream_writer_patch_needed():
        mocker.patch.object(aiohttp.ClientResponse, "__init__", _patched_client_response_init)

    with AioResponsesMock(passthrough=PASSTHROUGH_REQUESTS_PREFIXES) as mock:
        yield mock
