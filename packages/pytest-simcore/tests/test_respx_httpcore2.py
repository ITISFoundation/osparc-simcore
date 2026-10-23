import importlib
import importlib.util
from typing import Final

import pytest
import respx
from pytest_simcore import _HTTPCORE2_TARGETS
from respx.models import AllMockedAssertionError

_BASE_URL: Final = "https://test_respx_httpcore2"
_PATH: Final = "/foo"

# both forks stay mocked while they coexist, and only the installed one remains afterwards
_CLIENT_MODULES: Final[list[str]] = [name for name in ("httpx", "httpx2") if importlib.util.find_spec(name) is not None]


@pytest.mark.skipif(
    importlib.util.find_spec("httpcore2") is None,
    reason="requires httpcore2, installed together with httpx2",
)
def test_httpcore2_targets_resolve():
    # respx skips targets it cannot resolve, so a mistyped path would silently disable mocking
    for target in _HTTPCORE2_TARGETS:
        module_name, _, class_name = target.rpartition(".")
        assert hasattr(importlib.import_module(module_name), class_name), target


@pytest.mark.parametrize("client_name", _CLIENT_MODULES)
def test_respx_intercepts_client_requests(client_name: str):
    client_module = importlib.import_module(client_name)

    with respx.mock(base_url=_BASE_URL, assert_all_called=False, assert_all_mocked=True) as mock_router:
        mock_router.get(_PATH).respond(status_code=200, json={"ok": True})
        # NOTE: `_BASE_URL` resolves nowhere, so a request escaping the mock cannot pass
        response = client_module.get(f"{_BASE_URL}{_PATH}")

        assert response.status_code == 200
        assert response.json() == {"ok": True}
        assert len(mock_router.calls) == 1


@pytest.mark.parametrize("client_name", _CLIENT_MODULES)
async def test_respx_intercepts_async_client_requests(client_name: str):
    client_module = importlib.import_module(client_name)

    async with (
        respx.mock(base_url=_BASE_URL, assert_all_called=False, assert_all_mocked=True) as mock_router,
        client_module.AsyncClient() as client,
    ):
        mock_router.get(_PATH).respond(status_code=200, json={"ok": True})
        response = await client.get(f"{_BASE_URL}{_PATH}")

        assert response.status_code == 200
        assert response.json() == {"ok": True}
        assert len(mock_router.calls) == 1


@pytest.mark.parametrize("client_name", _CLIENT_MODULES)
def test_respx_refuses_requests_it_never_mocked(client_name: str):
    # without the httpcore2 targets this returns from a real DNS lookup instead of refusing
    client_module = importlib.import_module(client_name)

    with (
        respx.mock(base_url=_BASE_URL, assert_all_called=False, assert_all_mocked=True),
        pytest.raises(AllMockedAssertionError),
    ):
        client_module.get(f"{_BASE_URL}{_PATH}")
