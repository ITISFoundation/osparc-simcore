# pylint: disable=redefined-outer-name
"""Draft tests: DNS-gone must not consume the whole retry interval.

When a dynamic-sidecar swarm service is removed its DNS name
(`dy-sidecar_<uuid>`) stops resolving and every request fails with a
`ConnectError` raised during name resolution. `retry_on_errors` cannot tell
this from a transient connect blip and retries until `total_retry_interval`
elapses. During the 2026-11-17 disk-full incident this made every teardown of
a removed sidecar waste ~36 s in `containers:down` backoff failures
(`master-simcore_master_director-v2`, 09:25-09:30 UTC).

The fast-abort test encodes the proposed behavior (ticket P1 of
docs/issues/disk-full-resilience in the tracker repo) and is expected to fail
until it is implemented.
"""

import time
from collections.abc import AsyncIterator, Iterator
from typing import Final

import httpx2
import pytest
import respx
from httpx2 import Response
from servicelib.fastapi.http_client_thin import (
    BaseThinClient,
    ClientHttpError,
    retry_on_errors,
)
from servicelib.tracing import TracingConfig

_TOTAL_RETRY_INTERVAL: Final[float] = 10.0
_DEAD_HOST_URL: Final[str] = "http://dy-sidecar-5a4e3b2a1c0d4e5f8b9a0c1d2e3f4a5b:8000/containers:down"


class _ThickClient(BaseThinClient):
    @retry_on_errors()
    async def post_containers_down(self) -> Response:
        return await self.client.post(_DEAD_HOST_URL)


@pytest.fixture
async def thick_client() -> AsyncIterator[_ThickClient]:
    tracing_config = TracingConfig.create(service_name="test-client", tracing_settings=None)
    async with _ThickClient(total_retry_interval=_TOTAL_RETRY_INTERVAL, tracing_config=tracing_config) as client:
        yield client


@pytest.fixture
def dead_dns_name() -> Iterator[respx.MockRouter]:
    with respx.mock(assert_all_called=False) as respx_mock:
        respx_mock.post(_DEAD_HOST_URL).mock(side_effect=httpx2.ConnectError("[Errno -2] Name or service not known"))
        yield respx_mock


async def test_dns_gone_eventually_raises_within_retry_interval(
    thick_client: _ThickClient, dead_dns_name: respx.MockRouter
) -> None:
    # Pins the current behavior: bounded, but it consumes the full interval
    start = time.monotonic()
    with pytest.raises(ClientHttpError):
        await thick_client.post_containers_down()
    elapsed = time.monotonic() - start
    assert elapsed < _TOTAL_RETRY_INTERVAL * 2
    assert dead_dns_name.calls.call_count > 1


@pytest.mark.xfail(
    strict=False,
    reason="spec (P2): a name that no longer resolves will never resolve again; "
    "the client must abort after a bounded number of attempts instead of "
    "retrying for the full total_retry_interval",
)
async def test_dns_gone_aborts_before_full_retry_interval(
    thick_client: _ThickClient, dead_dns_name: respx.MockRouter
) -> None:
    start = time.monotonic()
    with pytest.raises(ClientHttpError):
        await thick_client.post_containers_down()
    elapsed = time.monotonic() - start
    assert elapsed < _TOTAL_RETRY_INTERVAL / 2
