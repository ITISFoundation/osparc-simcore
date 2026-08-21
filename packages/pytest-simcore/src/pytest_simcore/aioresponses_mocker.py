import inspect
import warnings
from collections.abc import Iterator
from typing import Any
from unittest.mock import Mock

import pytest
from aiohttp import ClientResponse
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

_ORIGINAL_CLIENT_RESPONSE_INIT = ClientResponse.__init__


def _is_stream_writer_patch_needed() -> bool:
    client_response_init_signature = inspect.signature(ClientResponse.__init__)
    stream_writer_parameter = client_response_init_signature.parameters.get("stream_writer")
    if stream_writer_parameter is None:
        return False
    return stream_writer_parameter.default is inspect.Parameter.empty


def _patched_client_response_init(self: ClientResponse, *args: Any, **kwargs: Any) -> None:
    kwargs.setdefault("stream_writer", Mock(output_size=0))
    _ORIGINAL_CLIENT_RESPONSE_INIT(self, *args, **kwargs)


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
    # Remove when aioresponses supports aiohttp's required stream_writer argument.
    if _is_stream_writer_patch_needed():
        warnings.warn(
            "aioresponses does not provide aiohttp's required stream_writer argument, therefore it is manually mocked. "
            "TIP: periodically check if it gets updated https://github.com/pnuckowski/aioresponses/issues/289",
            UserWarning,
            stacklevel=1,
        )
        mocker.patch.object(
            ClientResponse,
            "__init__",
            _patched_client_response_init,
        )

    with AioResponsesMock(passthrough=PASSTHROUGH_REQUESTS_PREFIXES) as mock:
        yield mock
