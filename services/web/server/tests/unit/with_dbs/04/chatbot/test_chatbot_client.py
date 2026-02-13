# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements


import json

import respx
from aiohttp.test_utils import TestClient
from faker import Faker
from pytest_simcore.helpers.typing_env import EnvVarsDict
from simcore_service_webserver.chatbot._client import (
    Message,
    ResponseMessage,
    get_chatbot_rest_client,
)
from simcore_service_webserver.chatbot.settings import ChatbotSettings


async def test_chatbot_client(
    app_environment: EnvVarsDict,
    client: TestClient,
    mocked_chatbot_api: respx.MockRouter,
    faker: Faker,
):
    assert client.app

    settings = ChatbotSettings.create_from_envs()
    assert settings.CHATBOT_HOST
    assert settings.CHATBOT_PORT

    chatbot_client = get_chatbot_rest_client(client.app)
    assert chatbot_client

    user_msg = Message(role="user", content=faker.sentence())
    developer_msg = Message(role="developer", content=faker.sentence())
    output = await chatbot_client.send(messages=[user_msg, developer_msg])
    assert isinstance(output, ResponseMessage)
    assert output.content == "42"
    _ = json.loads(mocked_chatbot_api.calls[0].request.content.decode())
