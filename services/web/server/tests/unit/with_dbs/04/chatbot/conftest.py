# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements

import itertools
import json
from collections.abc import AsyncIterator, Iterator
from typing import get_args

import httpx
import pytest
import respx
from aiohttp.test_utils import TestClient
from faker import Faker
from pydantic import TypeAdapter
from pytest_mock import MockerFixture, MockType
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.webserver_users import NewUser, UserInfoDict
from simcore_service_webserver.chatbot._client import (
    ChatResponse,
    ResponseItem,
    ResponseMessage,
)
from simcore_service_webserver.chatbot.settings import _CHATBOT_ARCHITECTURE, _CHATBOT_MODELS
from simcore_service_webserver.products import products_service


@pytest.fixture(
    params=list(itertools.product(get_args(_CHATBOT_MODELS), get_args(_CHATBOT_ARCHITECTURE))),
    ids=lambda p: f"model={p[0]}-arch={p[1]}",
)
def app_environment(
    request: pytest.FixtureRequest,
    monkeypatch: pytest.MonkeyPatch,
    app_environment: EnvVarsDict,
):
    chatmodel, chatarchitecture = request.param
    return app_environment | setenvs_from_dict(
        monkeypatch,
        {
            "WEBSERVER_CHATBOT": "{}",
            "CHATBOT_HOST": "chatbot",
            "CHATBOT_PORT": "8000",
            "CHATBOT_MODEL": chatmodel,
            "CHATBOT_GRAPH_NAME": chatarchitecture,
        },
    )


@pytest.fixture
def mocked_chatbot_api(faker: Faker) -> Iterator[respx.MockRouter]:
    _BASE_URL = "http://chatbot:8000"
    # Define responses in the order they will be called during the test
    chatbot_response = ChatResponse(
        id=f"{faker.uuid4()}",
        choices=[ResponseItem(index=0, message=ResponseMessage(content="42"))],
    )

    def _side_effect(request: httpx.Request) -> httpx.Response:
        # This function will be called for each request to the mocked endpoint
        # You can customize the response based on the request if needed
        request_body = json.loads(request.content)
        TypeAdapter(_CHATBOT_MODELS).validate_python(request_body.get("model"))
        metadata = request_body.get("metadata", {})
        TypeAdapter(_CHATBOT_ARCHITECTURE).validate_python(metadata.get("graph_name"))
        return httpx.Response(200, json=chatbot_response.model_dump(mode="json"))

    with respx.mock(base_url=_BASE_URL) as mock:
        # Create a side_effect that returns responses in sequence
        mock.post(path="/v1/chat/completions").mock(side_effect=_side_effect)
        yield mock


@pytest.fixture
async def chatbot_user(client: TestClient) -> AsyncIterator[UserInfoDict]:
    async with NewUser(
        user_data={
            "name": "chatbot user",
        },
        app=client.app,
    ) as user_info:
        yield user_info


@pytest.fixture
async def support_team_user(client: TestClient) -> AsyncIterator[UserInfoDict]:
    async with NewUser(
        user_data={
            "name": "support team user",
        },
        app=client.app,
    ) as user_info:
        yield user_info


@pytest.fixture
def mocked_get_current_product(chatbot_user: UserInfoDict, mocker: MockerFixture) -> MockType:
    mock = mocker.patch.object(products_service, "get_product")
    mocked_product = mocker.Mock()
    mocked_product.support_chatbot_user_id = chatbot_user["id"]
    mock.return_value = mocked_product
    return mock
