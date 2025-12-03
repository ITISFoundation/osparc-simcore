# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements

from collections.abc import Iterator

import httpx
import pytest
import respx
from pytest_mock import MockerFixture, MockType
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from simcore_service_webserver.chatbot._client import (
    ChatResponse,
    ResponseItem,
    ResponseMessage,
)
from simcore_service_webserver.products import products_service


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
        ChatResponse(
            choices=[ResponseItem(index=0, message=ResponseMessage(content="42"))]
        )
    ]

    with respx.mock(base_url=_BASE_URL) as mock:
        # Create a side_effect that returns responses in sequence
        mock.post(path="/v1/chat/completions").mock(
            side_effect=[
                httpx.Response(200, json=response.model_dump(mode="json"))
                for response in chatbot_answer_responses
            ]
        )
        yield mock


@pytest.fixture
def mocked_get_current_product(mocker: MockerFixture) -> MockType:
    mock = mocker.patch.object(products_service, "get_product")
    mocked_product = mocker.Mock()
    mocked_product.support_chatbot_user_id = 123
    mock.return_value = mocked_product
    return mock
