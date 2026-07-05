# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import pytest
import respx
from faker import Faker
from fastapi import FastAPI
from httpx import AsyncClient
from simcore_service_api_server.models.domain.chatbot import (
    ChatCompletionRequestMessage,
    CreateChatCompletionResponse,
    RoleEnum,
)
from simcore_service_api_server.services_http.chatbot import ChatbotApi

_CHATBOT_BASE_URL = "http://chatbot:8000"


@pytest.fixture
def chatbot_api() -> ChatbotApi:
    app = FastAPI()
    return ChatbotApi.create_once(
        app=app,
        client=AsyncClient(base_url=_CHATBOT_BASE_URL),
        service_name="chatbot",
    )


@pytest.fixture
def mocked_chatbot_backend():
    with respx.mock(base_url=_CHATBOT_BASE_URL, assert_all_mocked=True) as mock:
        yield mock


async def test_create_chat_completion(
    faker: Faker,
    mocked_chatbot_backend: respx.MockRouter,
    chatbot_api: ChatbotApi,
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

    result = await chatbot_api.create_chat_completion(
        messages=[
            ChatCompletionRequestMessage(role=RoleEnum.USER, content=user_message),
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
    chatbot_api: ChatbotApi,
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

    result = await chatbot_api.create_chat_completion(
        messages=[
            ChatCompletionRequestMessage(role=RoleEnum.DEVELOPER, content=developer_message),
            ChatCompletionRequestMessage(role=RoleEnum.USER, content=user_message),
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
    chatbot_api: ChatbotApi,
):
    mocked_chatbot_backend.post("/v1/chat/completions").respond(500)

    with pytest.raises(Exception):  # noqa: B017, PT011
        await chatbot_api.create_chat_completion(
            messages=[
                ChatCompletionRequestMessage(role=RoleEnum.USER, content=faker.sentence()),
            ],
            model="gpt-4o-mini",
            metadata={},
        )
