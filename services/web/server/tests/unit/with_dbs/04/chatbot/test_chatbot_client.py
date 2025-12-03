# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements


import respx
from aiohttp.test_utils import TestClient
from pytest_simcore.helpers.typing_env import EnvVarsDict
from simcore_service_webserver.chatbot._client import (
    ChatResponse,
    get_chatbot_rest_client,
)
from simcore_service_webserver.chatbot.settings import ChatbotSettings


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

    output = await chatbot_client.ask("What is the meaning of life?")
    assert isinstance(output, ChatResponse)
    assert output.answer == "42"
