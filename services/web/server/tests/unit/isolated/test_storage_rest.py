# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=protected-access

import pytest
from aiohttp import web
from aiohttp.test_utils import make_mocked_request
from servicelib.aiohttp.request_keys import RQT_USERID_KEY
from simcore_service_webserver.storage import _rest
from simcore_service_webserver.storage._rest import _to_storage_url
from yarl import URL

_STORAGE_BASE = "http://storage:8080/v0"


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
    ],
)
def test_encoded_delimiters_after_colon_stay_in_the_path(path: str, expected_raw_path: str, app: web.Application):
    request = _make_request(path, app)
    url = _to_storage_url(request)
    assert url.raw_path == expected_raw_path
    assert dict(url.query) == {"user_id": "42"}
