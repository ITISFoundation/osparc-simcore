# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements

from collections.abc import Iterator

import httpx
import pytest
import respx
from aiohttp.test_utils import TestClient
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from simcore_service_webserver.chatbot._client import (
    ChatResponse,
    get_chatbot_rest_client,
)
from simcore_service_webserver.chatbot.settings import ChatbotSettings


@pytest.fixture
def app_environment(
    monkeypatch: pytest.MonkeyPatch,
    app_environment: EnvVarsDict,
):
    return app_environment | setenvs_from_dict(
        monkeypatch,
        {
            "CHATBOT_HOST": "chatbot",
            "CHATBOT_PORT": "8000",
        },
    )


@pytest.fixture
def mocked_chatbot_api() -> Iterator[respx.MockRouter]:
    _BASE_URL = "http://chatbot:8000"

    # Define responses in the order they will be called during the test
    chatbot_answer_responses = [
        {"answer": "42"},
    ]

    with respx.mock(base_url=_BASE_URL) as mock:
        # Create a side_effect that returns responses in sequence
        mock.post(path="/v1/chat").mock(
            side_effect=[
                httpx.Response(200, json=response)
                for response in chatbot_answer_responses
            ]
        )
        yield mock


async def test_chatbot_client(
    app_environment: EnvVarsDict,
    client: TestClient,
    mocked_chatbot_api: respx.MockRouter,
):
    assert client.app

    settings = ChatbotSettings.create_from_envs()
    assert settings.CHATBOT_HOST
    assert settings.CHATBOT_PORT

    chatbot_client = get_chatbot_rest_client(client.app)
    assert chatbot_client

    output = await chatbot_client.ask_question("What is the meaning of life?")
    assert isinstance(output, ChatResponse)
    assert output.answer == "42"
