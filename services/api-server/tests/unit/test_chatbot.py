# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import json
from typing import Final

import httpx
import pytest
import respx
from faker import Faker
from fastapi import FastAPI
from httpx import AsyncClient
from pydantic import TypeAdapter
from simcore_service_api_server.core.settings import ChatbotSettings
from simcore_service_api_server.models.domain.chatbot import (
    ChatCompletionRequestMessage,
    CreateChatCompletionResponse,
)
from simcore_service_api_server.models.schemas.responses import InputMessage
from simcore_service_api_server.services_http.chatbot import ChatbotApi, ChatbotSession

_chat_message_adapter: Final = TypeAdapter(ChatCompletionRequestMessage)

_CHATBOT_BASE_URL: Final[str] = "http://chatbot:8000"
_GRAPH_NAME: Final[str] = "simple_rag"


@pytest.fixture
def chatbot_session() -> ChatbotSession:
    app = FastAPI()
    api = ChatbotApi.create_once(
        app=app,
        client=AsyncClient(base_url=_CHATBOT_BASE_URL),
        service_name="chatbot",
    )
    settings = ChatbotSettings(
        CHATBOT_URL=_CHATBOT_BASE_URL,
        GRAPH_NAME=_GRAPH_NAME,
    )
    return ChatbotSession(_chatbot_settings=settings, _api=api)


@pytest.fixture
def mocked_chatbot_backend():
    with respx.mock(base_url=_CHATBOT_BASE_URL, assert_all_mocked=True) as mock:
        yield mock


async def test_create_chat_completion(
    faker: Faker,
    mocked_chatbot_backend: respx.MockRouter,
    chatbot_session: ChatbotSession,
):
    expected_id = faker.uuid4()
    expected_answer = faker.sentence()
    user_message = faker.sentence()

    mocked_chatbot_backend.post("/v1/chat/completions").respond(
        200,
        json={
            "id": expected_id,
            "choices": [
                {
                    "index": 0,
                    "message": {"content": expected_answer},
                }
            ],
            "metadata": {"model": "gpt-4o-mini"},
            "question": [{"role": "user", "content": user_message}],
            "judgment": None,
            "comment": None,
        },
    )

    result = await chatbot_session.create_chat_completion(
        messages=[
            _chat_message_adapter.validate_python({"role": "user", "content": user_message}),
        ],
        model="gpt-4o-mini",
        metadata={},
    )

    assert isinstance(result, CreateChatCompletionResponse)
    assert result.id == expected_id
    assert len(result.choices) == 1
    assert result.choices[0].message.content == expected_answer
    assert result.metadata == {"model": "gpt-4o-mini"}


async def test_create_chat_completion_with_multiple_messages(
    faker: Faker,
    mocked_chatbot_backend: respx.MockRouter,
    chatbot_session: ChatbotSession,
):
    expected_id = faker.uuid4()
    expected_answer = faker.sentence()
    developer_message = faker.sentence()
    user_message = faker.sentence()

    mocked_chatbot_backend.post("/v1/chat/completions").respond(
        200,
        json={
            "id": expected_id,
            "choices": [
                {
                    "index": 0,
                    "message": {"content": expected_answer},
                }
            ],
            "metadata": {},
        },
    )

    result = await chatbot_session.create_chat_completion(
        messages=[
            _chat_message_adapter.validate_python({"role": "developer", "content": developer_message}),
            _chat_message_adapter.validate_python({"role": "user", "content": user_message}),
        ],
        model="gpt-4o-mini",
        metadata={"session": faker.word()},
        temperature=0.5,
    )

    assert result.id == expected_id
    assert result.choices[0].message.content == expected_answer

    # Verify the request was sent correctly
    request = mocked_chatbot_backend.calls[0].request
    assert request.url.path == "/v1/chat/completions"


async def test_create_chat_completion_raises_on_error(
    faker: Faker,
    mocked_chatbot_backend: respx.MockRouter,
    chatbot_session: ChatbotSession,
):
    mocked_chatbot_backend.post("/v1/chat/completions").respond(500)

    with pytest.raises(Exception):  # noqa: B017, PT011
        await chatbot_session.create_chat_completion(
            messages=[
                _chat_message_adapter.validate_python({"role": "user", "content": faker.sentence()}),
            ],
            model="gpt-4o-mini",
            metadata={},
        )


async def test_stream_chat_completion(
    faker: Faker,
    mocked_chatbot_backend: respx.MockRouter,
    chatbot_session: ChatbotSession,
):
    sse_body = b'data: {"choices":[{"delta":{"content":"hello"}}]}\n\ndata: [DONE]\n\n'
    mocked_chatbot_backend.post("/v1/chat/completions").respond(200, content=sse_body)

    response = await chatbot_session.stream_chat_completion(
        messages=[
            _chat_message_adapter.validate_python({"role": "user", "content": faker.sentence()}),
        ],
        model="gpt-4o-mini",
        metadata={},
    )

    assert response.status_code == 200
    received = b"".join([chunk async for chunk in response.aiter_bytes()])
    await response.aclose()

    assert received == sse_body

    request = mocked_chatbot_backend.calls[0].request
    assert request.url.path == "/v1/chat/completions"
    assert json.loads(request.content)["stream"] is True


async def test_stream_chat_completion_sends_graph_name_in_metadata(
    faker: Faker,
    mocked_chatbot_backend: respx.MockRouter,
    chatbot_session: ChatbotSession,
):
    mocked_chatbot_backend.post("/v1/chat/completions").respond(200, content=b"data: [DONE]\n\n")
    metadata = {"session_id": faker.uuid4()}

    response = await chatbot_session.stream_chat_completion(
        messages=[
            _chat_message_adapter.validate_python({"role": "user", "content": faker.sentence()}),
        ],
        model="gpt-4o-mini",
        metadata=metadata,
    )
    await response.aread()
    await response.aclose()

    request_body = json.loads(mocked_chatbot_backend.calls[0].request.content)
    assert request_body["metadata"] == {
        "session_id": metadata["session_id"],
        "graph_name": _GRAPH_NAME,
    }
    assert metadata == {"session_id": metadata["session_id"]}


async def test_stream_chat_completion_raises_on_error(
    faker: Faker,
    mocked_chatbot_backend: respx.MockRouter,
    chatbot_session: ChatbotSession,
):
    mocked_chatbot_backend.post("/v1/chat/completions").respond(500, text="downstream error")

    with pytest.raises(httpx.HTTPStatusError) as exc_info:
        await chatbot_session.stream_chat_completion(
            messages=[
                _chat_message_adapter.validate_python({"role": "user", "content": faker.sentence()}),
            ],
            model="gpt-4o-mini",
            metadata={},
        )

    # body must already be readable even though stream_chat_completion closed the response
    assert exc_info.value.response.text == "downstream error"


@pytest.mark.parametrize("role", ["user", "assistant", "developer"])
def test_input_message_to_domain_model(faker: Faker, role: str):
    msg = InputMessage(role=role, content=faker.sentence(), name=faker.first_name())
    domain_msg = msg.to_domain_model()

    assert domain_msg.role == role
    assert domain_msg.content == msg.content
    if hasattr(domain_msg, "name"):
        assert domain_msg.name == msg.name
