# pylint:disable=redefined-outer-name
"""Fixtures mocking a remote HTTP API with `respx` (opt-in plugin).

Interception also covers `httpx2` clients thanks to the httpcore2 seam set up in
`pytest_simcore.pytest_configure` (https://github.com/ITISFoundation/osparc-simcore/issues/9927).
"""

from collections.abc import Iterator

import pytest
import respx


@pytest.fixture
def mocked_api_base_url() -> str:
    """Synthetic base URL of the mocked API. Override to match the base_url of the client under test."""
    return "https://mocked_api.test"


@pytest.fixture
def mocked_api_router(mocked_api_base_url: str) -> Iterator[respx.MockRouter]:
    """Mocks `mocked_api_base_url` and rejects every request not routed here.

    The router is yielded empty: consumers register their own routes (e.g.
    `router.get("/foo").respond(200)`) before making requests. Both checks run at
    request time: an unrouted request to `mocked_api_base_url` fails the test
    instead of silently reaching the network, and so does any request to another host.
    """
    with respx.mock(
        base_url=mocked_api_base_url,
        assert_all_called=False,
        assert_all_mocked=True,  # IMPORTANT: KEEP always True!
    ) as router:
        yield router
