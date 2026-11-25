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
    request = make_mocked_request("GET", path, app=app)
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
    ],
)
def test_encoded_dot_segments_are_rejected(path: str, app: web.Application):
    request = _make_request(path, app)
    with pytest.raises(web.HTTPBadRequest):
        _to_storage_url(request)


@pytest.mark.parametrize(
    "path, expected_storage_path",
    [
        ("/v0/storage/locations/0/files/%2e%2e/status", "/v0/locations/0/status"),
        ("/v0/storage/locations/0/files/..", "/v0/locations/0/"),
    ],
)
def test_whole_segment_dots_stay_inside_base(path: str, expected_storage_path: str, app: web.Application):
    request = _make_request(path, app)
    url = _to_storage_url(request)
    assert url.path == expected_storage_path
