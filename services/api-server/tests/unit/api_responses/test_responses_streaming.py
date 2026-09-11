# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name
# pylint: disable=no-name-in-module

from collections.abc import Iterator
from unittest.mock import MagicMock

import pytest
import respx
from fastapi import FastAPI, status
from httpx import AsyncClient, BasicAuth
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from servicelib.celery.task_manager import TaskManager
from simcore_service_api_server._meta import API_VTAG
from simcore_service_api_server.api.dependencies.celery import get_task_manager

_CHATBOT_BASE_URL = "http://chatbot:8000"
_CHAT_MODEL = "gpt-4o-mini"


@pytest.fixture
def app_environment(app_environment: EnvVarsDict, monkeypatch: pytest.MonkeyPatch) -> EnvVarsDict:
    """Only the chatbot needs to be enabled; the streaming branch never touches celery."""
    return setenvs_from_dict(
        monkeypatch,
        {"API_SERVER_CHATBOT": '{"CHATBOT_URL": "http://chatbot:8000", "GRAPH_NAME": "simple_rag"}'},
    )


@pytest.fixture
def app(app: FastAPI) -> Iterator[FastAPI]:
    """The route still resolves the `TaskManager` dependency even though the streaming
    branch never uses it, so bypass it instead of standing up a real celery app."""
    app.dependency_overrides[get_task_manager] = lambda: MagicMock(spec=TaskManager)
    yield app
    app.dependency_overrides.pop(get_task_manager, None)


@pytest.fixture
def mocked_chatbot_backend():
    with respx.mock(base_url=_CHATBOT_BASE_URL, assert_all_mocked=True) as mock:
        yield mock


async def test_create_response_stream_relays_sse_bytes(
    app: FastAPI,
    client: AsyncClient,
    auth: BasicAuth,
    mocked_chatbot_backend: respx.MockRouter,
):
    # ARRANGE
    sse_body = b'data: {"choices":[{"delta":{"content":"hello"}}]}\n\ndata: [DONE]\n\n'
    mocked_chatbot_backend.post("/v1/chat/completions").respond(
        200,
        content=sse_body,
        headers={"content-type": "text/event-stream"},
    )

    body = {
        "background": True,
        "stream": True,
        "input": [{"role": "user", "content": "Hello, how are you?"}],
        "model": _CHAT_MODEL,
        "temperature": 0.7,
    }

    # ACT
    response = await client.post(
        f"/{API_VTAG}/responses",
        auth=auth,
        json=body,
    )

    # ASSERT
    assert response.status_code == status.HTTP_200_OK
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.content == sse_body

    downstream_request = mocked_chatbot_backend.calls[0].request
    assert downstream_request.url.path == "/v1/chat/completions"


async def test_create_response_stream_relays_downstream_client_error(
    app: FastAPI,
    client: AsyncClient,
    auth: BasicAuth,
    mocked_chatbot_backend: respx.MockRouter,
):
    # ARRANGE - the chatbot service rejects the request (e.g. failed its own validation)
    mocked_chatbot_backend.post("/v1/chat/completions").respond(
        status.HTTP_422_UNPROCESSABLE_ENTITY,
        json={"detail": [{"loc": ["body", "model"], "msg": "unsupported model", "type": "value_error"}]},
    )

    body = {
        "background": True,
        "stream": True,
        "input": [{"role": "user", "content": "Hello"}],
        "model": _CHAT_MODEL,
        "temperature": 0.7,
    }

    # ACT
    response = await client.post(
        f"/{API_VTAG}/responses",
        auth=auth,
        json=body,
    )

    # ASSERT - the downstream client error is relayed as-is, not masked as a backend error
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    payload = response.json()
    assert payload["errors"] == [{"loc": ["body", "model"], "msg": "unsupported model", "type": "value_error"}]


async def test_create_response_stream_downstream_server_error_returns_bad_gateway(
    app: FastAPI,
    client: AsyncClient,
    auth: BasicAuth,
    mocked_chatbot_backend: respx.MockRouter,
):
    # ARRANGE - the chatbot service itself fails
    mocked_chatbot_backend.post("/v1/chat/completions").respond(status.HTTP_500_INTERNAL_SERVER_ERROR)

    body = {
        "background": True,
        "stream": True,
        "input": [{"role": "user", "content": "Hello"}],
        "model": _CHAT_MODEL,
        "temperature": 0.7,
    }

    # ACT
    response = await client.post(
        f"/{API_VTAG}/responses",
        auth=auth,
        json=body,
    )

    # ASSERT - 5xx downstream errors are translated to a generic backend error, not relayed
    assert response.status_code == status.HTTP_502_BAD_GATEWAY
    payload = response.json()
    assert "errors" in payload
