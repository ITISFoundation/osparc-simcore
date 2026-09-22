# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import re
from collections.abc import AsyncIterator

import httpx2
import pytest
from faker import Faker
from fastapi_pagination import LimitOffsetPage, LimitOffsetParams
from servicelib.aiohttp import status
from simcore_service_storage.modules.datcore_adapter.datcore_adapter_settings import (
    DatcoreAdapterSettings,
)


@pytest.fixture
async def datcore_adapter_service_mock(
    faker: Faker, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[httpx2.MockTransport]:
    """Mocks the datcore-adapter service's HTTP API using ``httpx2.MockTransport``.

    NOTE: respx cannot intercept httpx2 traffic (httpx2.AsyncClient is not an
    httpx.AsyncClient subclass), therefore the mock is installed by replacing
    the httpx2.AsyncHTTPTransport factory used by servicelib.fastapi.httpx_client
    while this fixture is active. Any request NOT addressed to the datcore-adapter
    endpoint is passed through to the real transport.
    """
    dat_core_settings = DatcoreAdapterSettings.create_from_envs()
    base_url = httpx2.URL(dat_core_settings.endpoint)

    # created before patching httpx2.AsyncHTTPTransport below
    real_transport = httpx2.AsyncHTTPTransport(http2=True)

    def _mocked_response(path: str) -> httpx2.Response:
        if path == "/user/profile":
            return httpx2.Response(status.HTTP_200_OK, json=faker.pydict(allowed_types=(str,)))

        if re.search(r"/datasets/[^/]+/files_legacy", path):
            return httpx2.Response(status.HTTP_200_OK, json=[])

        if "/datasets" in path:
            return httpx2.Response(
                status.HTTP_200_OK,
                json=LimitOffsetPage.create(items=[], params=LimitOffsetParams(limit=10, offset=0), total=0).model_dump(
                    mode="json"
                ),
            )

        if file_id_match := re.search(r"/files/([^/]+)", path):
            return httpx2.Response(
                status.HTTP_404_NOT_FOUND,
                json={"error": f"{file_id_match.group(1)} not found!"},
            )

        if path == "/":
            return httpx2.Response(status.HTTP_200_OK, json={"message": "ok"})

        return httpx2.Response(status.HTTP_404_NOT_FOUND, json={"error": f"{path} is not mocked"})

    async def _handler(request: httpx2.Request) -> httpx2.Response:
        url = request.url
        if url.host != base_url.host or url.port != base_url.port or not url.path.startswith(base_url.path):
            # NOTE: passthrough anything not addressed to the datcore-adapter service
            return await real_transport.handle_async_request(request)
        return _mocked_response(url.path.removeprefix(base_url.path) or "/")

    mock_transport = httpx2.MockTransport(handler=_handler)

    # The app's shared httpx2 client (servicelib.fastapi.httpx_client) is created with an
    # explicit httpx2.AsyncHTTPTransport: swap it for the mock while this fixture is active.
    def _mock_transport_factory(*_args, **_kwargs):
        return mock_transport

    monkeypatch.setattr(httpx2, "AsyncHTTPTransport", _mock_transport_factory)

    try:
        yield mock_transport
    finally:
        await real_transport.aclose()
