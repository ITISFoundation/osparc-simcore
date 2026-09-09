# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import pytest
from celery.contrib.testing.worker import TestWorkController  # type: ignore # pylint: disable=no-name-in-module
from fastapi import FastAPI, status
from httpx import AsyncClient, BasicAuth
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from simcore_service_api_server._meta import API_VTAG

pytest_simcore_core_services_selection = [
    "postgres",
    "rabbit",
]
pytest_simcore_ops_services_selection = ["adminer"]


@pytest.fixture
def app_environment(
    app_environment: EnvVarsDict,
    monkeypatch: pytest.MonkeyPatch,
) -> EnvVarsDict:
    """Override to ensure chatbot is NOT configured."""
    return setenvs_from_dict(
        monkeypatch,
        {"API_SERVER_CHATBOT": "null"},
    )


async def test_create_response_returns_503_when_chatbot_disabled(
    app: FastAPI,
    client: AsyncClient,
    auth: BasicAuth,
    with_api_server_celery_worker: TestWorkController,
):
    assert app.state.settings.API_SERVER_CHATBOT is None

    body = {
        "background": True,
        "input": [{"role": "user", "content": "Hello"}],
        "model": "gpt-4o-mini",
        "temperature": 0.7,
    }

    response = await client.post(
        f"/{API_VTAG}/responses",
        auth=auth,
        json=body,
    )

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
