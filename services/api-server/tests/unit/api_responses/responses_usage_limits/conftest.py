# pylint: disable=protected-access
# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name
# pylint: disable=no-name-in-module

"""Shared fixtures for the Chatbox usage-limits tests (streaming + Celery paths).

Seam: the api-server HTTP API of the /responses routes, with a faked Chatbox upstream
(respx) and a fake Redis (fakeredis, via use_in_memory_redis). No unit tests of the
internal counter helpers.
"""

import json
from types import SimpleNamespace

import pytest
import respx
from fastapi import FastAPI
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from settings_library.redis import RedisSettings
from simcore_service_api_server.clients.chatbot_usage import get_chatbot_usage_ledger

CHATBOT_BASE_URL = "http://chatbot:8000"
CHAT_MODEL = "gpt-4o-mini"

GLOBAL_KEY = "api-server:chatbot:usage:global"
WINDOW_KEY_PATTERN = "api-server:chatbot:usage:window:*"
RATE_KEY_PREFIX = "api-server:chatbot:rate"


def _make_sse_with_usage(prompt_tokens: int, completion_tokens: int, *, content: str = "hi") -> bytes:
    total = prompt_tokens + completion_tokens
    first = json.dumps({"id": "r", "choices": [{"index": 0, "delta": {"content": content}}]})
    usage = json.dumps(
        {
            "id": "r",
            "choices": [],
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total,
            },
        }
    )
    return f"data: {first}\n\ndata: {usage}\n\ndata: [DONE]\n\n".encode()


def _make_sse_without_usage(content: str = "the answer") -> bytes:
    first = json.dumps({"id": "r", "choices": [{"index": 0, "delta": {"content": content}}]})
    return f"data: {first}\n\ndata: [DONE]\n\n".encode()


def _make_stream_body(content: str = "Hello") -> dict:
    return {
        "background": True,
        "stream": True,
        "input": [{"role": "user", "content": content}],
        "model": CHAT_MODEL,
        "temperature": 0.7,
    }


def _make_background_body(content: str = "Hello") -> dict:
    return {
        "background": True,
        "input": [{"role": "user", "content": content}],
        "model": CHAT_MODEL,
        "temperature": 0.7,
    }


def _make_limits_env(**overrides: object) -> str:
    params = {"REDIS": {}, "PROVIDER_BUDGET_USD": 1000, **overrides}
    return json.dumps(params)


@pytest.fixture
def usage_builders():
    """SSE/request-body builders and key constants shared by the usage-limits tests."""
    return SimpleNamespace(
        make_sse_with_usage=_make_sse_with_usage,
        make_sse_without_usage=_make_sse_without_usage,
        make_stream_body=_make_stream_body,
        make_background_body=_make_background_body,
        make_limits_env=_make_limits_env,
        chatbot_base_url=CHATBOT_BASE_URL,
        global_key=GLOBAL_KEY,
        window_key_pattern=WINDOW_KEY_PATTERN,
        rate_key_prefix=RATE_KEY_PREFIX,
    )


@pytest.fixture
def app_environment(
    request: pytest.FixtureRequest,
    app_environment: EnvVarsDict,
    use_in_memory_redis: RedisSettings,
    monkeypatch: pytest.MonkeyPatch,
) -> EnvVarsDict:
    """Chatbot + usage limits against a fake Redis. Override the limits per test with
    @pytest.mark.parametrize("app_environment", [...], indirect=True)."""
    overrides: dict = getattr(request, "param", None) or {"WINDOW_SPEND_USD": 0.003}
    return setenvs_from_dict(
        monkeypatch,
        {
            "API_SERVER_CHATBOT": '{"CHATBOT_URL": "http://chatbot:8000", "GRAPH_NAME": "simple_rag"}',
            "API_SERVER_CHATBOT_USAGE_LIMITS": _make_limits_env(**overrides),
        },
    )


@pytest.fixture
def mocked_chatbot_backend():
    # assert_all_called=False: blocked requests must NEVER reach the Chatbox
    with respx.mock(base_url=CHATBOT_BASE_URL, assert_all_called=False, assert_all_mocked=False) as mock:
        yield mock


@pytest.fixture
async def read_ledger_state(app: FastAPI):
    """Raw reads of the window hashes / global hash for post-assertions."""

    async def _read() -> dict:
        ledger = get_chatbot_usage_ledger(app)
        assert ledger is not None
        redis = ledger._client.redis  # noqa: SLF001
        windows: dict[str, dict[str, float]] = {}
        async for key in redis.scan_iter(WINDOW_KEY_PATTERN):
            windows[f"{key}"] = {field: float(value) for field, value in (await redis.hgetall(key)).items()}
        global_stats = {field: float(value) for field, value in (await redis.hgetall(GLOBAL_KEY)).items()}
        return {"windows": windows, "global": global_stats}

    return _read


@pytest.fixture
async def fresh_usage_ledger(client, app: FastAPI):
    """Fake Redis clients from the same DSN share one server: flush between tests so
    Usage Windows stay independent. Applied via pytest.mark.usefixtures in each module
    (autouse is banned in conftest.py)."""
    yield
    ledger = get_chatbot_usage_ledger(app)
    assert ledger is not None
    await ledger._client.redis.flushall()  # noqa: SLF001
