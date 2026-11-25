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


async def test_regular_file_url_is_translated(app: web.Application) -> None:
    request = _make_request("/v0/storage/locations/0/files/api/0/6bc1e6ad/proj/file.txt?file_size=42", app)
    assert _to_storage_url(request) == URL(
        f"{_STORAGE_BASE}/locations/0/files/api/0/6bc1e6ad/proj/file.txt?file_size=42&user_id=42"
    )


async def test_action_verb_suffix_is_kept_raw(app: web.Application) -> None:
    request = _make_request("/v0/storage/locations/0/files/api/0/6bc1e6ad/proj/file.txt:complete", app)
    assert _to_storage_url(request).raw_path.startswith("/v0/locations/0/files/api/0/6bc1e6ad/proj/file.txt:complete")


@pytest.mark.parametrize(
    "path",
    [
        # %2f-encoded separators keep the dot components inside one path
        # segment, which quote(safe='/') would re-expose to joinpath
        # (the SEC-WS-49 traversal)
        "/v0/storage/locations/0/files/..%2f..%2f..%2f..%2fstatus",
        "/v0/storage/locations/0/files/%2e%2e%2f%2e%2e%2fstatus",
        "/v0/storage/locations/0/files/.%2fstatus",
    ],
)
async def test_encoded_dot_segments_are_rejected(path: str, app: web.Application) -> None:
    request = _make_request(path, app)
    with pytest.raises(web.HTTPBadRequest):
        _to_storage_url(request)


@pytest.mark.parametrize(
    ("path", "expected_storage_path"),
    [
        # whole-segment dots are normalized away at URL parsing (yarl), so no
        # escape ever reaches the builder — result must stay inside the base
        ("/v0/storage/locations/0/files/%2e%2e/status", "/v0/locations/0/status"),
        ("/v0/storage/locations/0/files/..", "/v0/locations/0/"),
    ],
)
async def test_whole_segment_dots_stay_inside_base(path: str, expected_storage_path: str, app: web.Application) -> None:
    request = _make_request(path, app)
    url = _to_storage_url(request)
    assert url.path == expected_storage_path
