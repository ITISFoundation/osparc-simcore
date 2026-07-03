import inspect
import warnings
from unittest.mock import Mock

import aiohttp

orig = aiohttp.ClientResponse.__init__


def is_stream_writer_patch_needed() -> bool:
    return "stream_writer" in inspect.signature(orig).parameters


def patched_client_response_init(self, *args, **kwargs):
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
    orig(self, *args, **kwargs)
