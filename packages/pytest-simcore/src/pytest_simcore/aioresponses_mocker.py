from collections.abc import Iterator
from unittest.mock import Mock

import pytest
from aioresponses import aioresponses as AioResponsesMock  # noqa: N812
from aioresponses.core import RequestMatch

from .helpers.host import get_localhost_ip

# WARNING: any request done through the client will go through aioresponses. It is
# unfortunate but that means any valid request (like calling the test server) prefix must be set as passthrough.
# Other than that it seems to behave nicely
PASSTHROUGH_REQUESTS_PREFIXES = [
    "http://127.0.0.1",
    "ws://",
    f"http://{get_localhost_ip()}",
]


def _patch_aioresponses_for_aiohttp_314():
    """Monkey-patch aioresponses to work with aiohttp>=3.14.0.

    aiohttp 3.14.0 added a required `stream_writer` keyword argument to
    ClientResponse.__init__(). The aioresponses library constructs
    ClientResponse objects directly in RequestMatch._build_response without
    passing this argument, causing TypeError at runtime.

    This patch injects a mock `stream_writer` into the kwargs before
    ClientResponse is instantiated.

    SEE https://github.com/pnuckowski/aioresponses/issues/290
    """
    _original_build_response = RequestMatch._build_response

    def _patched_build_response(self, *args, **kwargs):
        # Intercept to inject stream_writer into the internal kwargs
        original_init = self.response_class.__init__ if self.response_class else None

        import aiohttp

        _orig_cr_init = aiohttp.ClientResponse.__init__

        def _init_with_stream_writer(self_resp, *a, **kw):
            if "stream_writer" not in kw:
                mock_writer = Mock()
                mock_writer.output_size = 0
                kw["stream_writer"] = mock_writer
            return _orig_cr_init(self_resp, *a, **kw)

        aiohttp.ClientResponse.__init__ = _init_with_stream_writer  # type: ignore[assignment]
        try:
            return _original_build_response(self, *args, **kwargs)
        finally:
            aiohttp.ClientResponse.__init__ = _orig_cr_init  # type: ignore[assignment]

    RequestMatch._build_response = _patched_build_response  # type: ignore[assignment]


_patch_aioresponses_for_aiohttp_314()


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
