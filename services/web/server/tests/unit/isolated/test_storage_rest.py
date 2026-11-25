# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=protected-access

from collections.abc import Callable
from typing import Final, NamedTuple

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, make_mocked_request
from servicelib.aiohttp import status
from servicelib.aiohttp.request_keys import RQT_USERID_KEY
from simcore_service_webserver.storage import _rest
from simcore_service_webserver.storage._rest import _forward_request_to_storage, _to_storage_url
from yarl import URL

_STORAGE_BASE: Final[str] = "http://storage:8080/v0"


class _SpiedRequest(NamedTuple):
    method: str
    path: str
    query: dict[str, str]


class _StorageProxy(NamedTuple):
    client: TestClient
    spied: list[_SpiedRequest]


@pytest.fixture
def app(monkeypatch: pytest.MonkeyPatch) -> web.Application:
    app_ = web.Application()
    monkeypatch.setattr(_rest, "_get_base_storage_url", lambda _app: URL(_STORAGE_BASE, encoded=True))
    return app_


def _make_request(path: str, app: web.Application, user_id: int = 42) -> web.Request:
    # mirror aiohttp's HTTP parser, which builds the request URL with
    # URL(path, encoded=True); make_mocked_request's URL(path) would percent-decode
    # and remove dot-segments at parse time, hiding traversal shapes from the handler
    request = make_mocked_request("GET", "/", app=app).clone(rel_url=URL(f"http://127.0.0.1{path}", encoded=True))
    request[RQT_USERID_KEY] = user_id
    return request


def test_regular_file_url_is_translated(app: web.Application):
    request = _make_request("/v0/storage/locations/0/files/api/0/6bc1e6ad/proj/file.txt?file_size=42", app)
    assert _to_storage_url(request) == URL(
        f"{_STORAGE_BASE}/locations/0/files/api/0/6bc1e6ad/proj/file.txt?file_size=42&user_id=42"
    )


def test_product_name_is_appended_as_query_param(app: web.Application):
    request = _make_request("/v0/storage/locations/0/paths", app)
    url = _to_storage_url(request, product_name="osparc")
    assert url.query["product_name"] == "osparc"
    assert url.query["user_id"] == "42"


def test_proxy_identity_query_params_win_over_client_values(app: web.Application):
    request = _make_request("/v0/storage/locations?user_id=7&user_id=8&product_name=evil", app)
    url = _to_storage_url(request, product_name="osparc")
    assert url.query.getall("user_id") == ["42"]
    assert url.query.getall("product_name") == ["osparc"]


def test_action_verb_suffix_is_kept_raw(app: web.Application):
    request = _make_request("/v0/storage/locations/0/files/api/0/6bc1e6ad/proj/file.txt:complete?file_size=42", app)
    url = _to_storage_url(request)
    assert url.raw_path == "/v0/locations/0/files/api/0/6bc1e6ad/proj/file.txt:complete"
    assert url.query["file_size"] == "42"


@pytest.mark.parametrize(
    "path",
    [
        "/v0/storage/locations/0/files/..%2f..%2f..%2f..%2fstatus",
        "/v0/storage/locations/0/files/%2e%2e%2f%2e%2e%2fstatus",
        "/v0/storage/locations/0/files/.%2fstatus",
        "/v0/storage/locations/0/files/%2e%2e/status",
        "/v0/storage/locations/0/files/..",
    ],
)
def test_dot_segments_are_rejected(path: str, app: web.Application):
    request = _make_request(path, app)
    with pytest.raises(web.HTTPBadRequest):
        _to_storage_url(request)


@pytest.mark.parametrize(
    "segment",
    ["...", ".hidden", "a...b"],
)
def test_dot_like_names_are_allowed(segment: str, app: web.Application):
    request = _make_request(f"/v0/storage/locations/0/files/{segment}", app)
    assert _to_storage_url(request).path == f"/v0/locations/0/files/{segment}"


@pytest.mark.parametrize(
    "path, expected_raw_path",
    [
        # decoded '?', '#' and ' ' after the ':action' colon must stay inside the
        # path: on the wire the first '?' would start the query and let the
        # injected user_id take precedence over the proxy-appended one
        (
            "/v0/storage/locations/0/files/api/0/uuid/foo:abort%3Fuser_id%3D7%26x%3D:complete",
            "/v0/locations/0/files/api/0/uuid/foo:abort%3Fuser_id%3D7%26x%3D:complete",
        ),
        (
            "/v0/storage/locations/0/files/x:a%23b:complete",
            "/v0/locations/0/files/x:a%23b:complete",
        ),
        (
            "/v0/storage/locations/0/files/x:a%20b:abort",
            "/v0/locations/0/files/x:a%20b:abort",
        ),
        # action in the middle of the path, with segments trailing it
        (
            "/v0/storage/locations/0/files/api/0/uuid/proj/f.txt:complete/futures/abc123",
            "/v0/locations/0/files/api/0/uuid/proj/f.txt:complete/futures/abc123",
        ),
        (
            "/v0/storage/locations/0/files/api/0/uuid/proj/f.txt:complete/futures/abc%3Fuser_id%3D7",
            "/v0/locations/0/files/api/0/uuid/proj/f.txt:complete/futures/abc%3Fuser_id%3D7",
        ),
        (
            "/v0/storage/locations/0/files/foo:abort%3Fuser_id%3D7%26x%3D:complete/futures/abc123",
            "/v0/locations/0/files/foo:abort%3Fuser_id%3D7%26x%3D:complete/futures/abc123",
        ),
    ],
)
def test_encoded_delimiters_after_colon_stay_in_the_path(path: str, expected_raw_path: str, app: web.Application):
    request = _make_request(path, app)
    url = _to_storage_url(request)
    assert url.raw_path == expected_raw_path
    assert dict(url.query) == {"user_id": "42"}


@pytest.fixture
def create_storage_proxy(aiohttp_client: Callable, monkeypatch: pytest.MonkeyPatch):
    async def _create() -> _StorageProxy:
        spied: list[_SpiedRequest] = []

        async def _storage_spy(request: web.Request) -> web.Response:
            # path and query are what storage's framework routes on
            spied.append(_SpiedRequest(request.method, request.path, dict(request.query)))
            return web.json_response({"data": "ok", "links": None, "meta": None})

        spy_app = web.Application()
        spy_app.router.add_route("*", "/{tail:.*}", _storage_spy)
        spy_client: TestClient = await aiohttp_client(spy_app)

        monkeypatch.setattr(
            _rest, "_get_base_storage_url", lambda _app: URL(f"{spy_client.make_url('/v0')}", encoded=True)
        )
        monkeypatch.setattr(_rest, "get_client_session", lambda _app: spy_client.session)

        async def _proxy(request: web.Request) -> web.Response:
            request[RQT_USERID_KEY] = 42
            payload, resp_status = await _forward_request_to_storage(request, request.method, body=None)
            return web.json_response(payload, status=resp_status)

        app_ = web.Application()
        app_.router.add_route("*", "/{tail:.*}", _proxy)
        client = await aiohttp_client(app_)
        return _StorageProxy(client=client, spied=spied)

    return _create


async def test_encoded_traversal_is_rejected_over_http(create_storage_proxy: Callable):
    proxy = await create_storage_proxy()

    resp = await proxy.client.get("/v0/storage/locations/0/files/..%2f..%2f..%2f..%2fstatus")
    assert resp.status == status.HTTP_400_BAD_REQUEST
    assert "must not contain" in await resp.text()
    assert not proxy.spied

    resp = await proxy.client.get("/v0/storage/locations")
    assert resp.status == status.HTTP_200_OK
    assert proxy.spied == [_SpiedRequest("GET", "/v0/locations", {"user_id": "42"})]


async def test_encoded_action_delimiters_reach_storage_in_the_path(create_storage_proxy: Callable):
    proxy = await create_storage_proxy()

    resp = await proxy.client.post("/v0/storage/locations/0/files/api/0/uuid/foo:abort%3Fuser_id%3D7%26x%3D:complete")
    assert resp.status == status.HTTP_200_OK
    assert proxy.spied[-1] == _SpiedRequest(
        "POST",
        "/v0/locations/0/files/api/0/uuid/foo:abort?user_id=7&x=:complete",
        {"user_id": "42"},
    )

    resp = await proxy.client.post(
        "/v0/storage/locations/0/files/api/0/uuid/proj/f.txt:complete/futures/abc%3Fuser_id%3D7"
    )
    assert resp.status == status.HTTP_200_OK
    assert proxy.spied[-1] == _SpiedRequest(
        "POST",
        "/v0/locations/0/files/api/0/uuid/proj/f.txt:complete/futures/abc?user_id=7",
        {"user_id": "42"},
    )
