# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name
# pylint: disable=no-name-in-module
# pylint: disable=too-many-positional-arguments


import datetime

import pytest
import respx
from celery.contrib.testing.worker import TestWorkController  # type: ignore # pylint: disable=no-name-in-module
from fastapi import FastAPI, status
from httpx import AsyncClient, BasicAuth
from simcore_service_api_server._meta import API_VTAG
from simcore_service_api_server.models.schemas.responses import (
    ResponseObject,
    ResponseStatus,
)
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_delay,
    wait_fixed,
)

pytest_simcore_core_services_selection = [
    "postgres",
    "rabbit",
]
pytest_simcore_ops_services_selection = ["adminer"]

_CHATBOT_BASE_URL = "http://chatbot:8000"
_CHAT_MODEL = "gpt-4o-mini"


@pytest.fixture
def mocked_chatbot_backend():
    with respx.mock(base_url=_CHATBOT_BASE_URL, assert_all_mocked=True) as mock:
        yield mock


async def test_create_response_with_celery_workflow(
    app: FastAPI,
    client: AsyncClient,
    auth: BasicAuth,
    with_api_server_celery_worker: TestWorkController,
    mocked_chatbot_backend: respx.MockRouter,
):
    # ARRANGE
    expected_answer = "This is the chatbot response."
    mocked_chatbot_backend.post("/v1/chat/completions").respond(
        200,
        json={
            "id": "fake-completion-id",
            "choices": [{"index": 0, "message": {"content": expected_answer}}],
        },
    )

    body = {
        "background": True,
        "input": [
            {"role": "user", "content": "Hello, how are you?"},
        ],
        "model": _CHAT_MODEL,
        "temperature": 0.7,
    }

    # ACT - create response (submit task)
    response = await client.post(
        f"/{API_VTAG}/responses",
        auth=auth,
        json=body,
    )

    # ASSERT - response is queued
    assert response.status_code == status.HTTP_200_OK
    response_obj = ResponseObject.model_validate(response.json())
    assert response_obj.status == ResponseStatus.QUEUED
    assert response_obj.model == _CHAT_MODEL
    assert response_obj.background is True
    response_id = response_obj.id

    # ACT - poll GET /responses/{id} until completed
    async for attempt in AsyncRetrying(
        stop=stop_after_delay(30),
        wait=wait_fixed(wait=datetime.timedelta(seconds=1.0)),
        reraise=True,
        retry=retry_if_exception_type(AssertionError),
    ):
        with attempt:
            response = await client.get(
                f"/{API_VTAG}/responses/{response_id}",
                auth=auth,
            )
            if response.status_code != status.HTTP_200_OK:
                pytest.fail(f"GET /responses/{response_id} failed with {response.status_code}")
            response_obj = ResponseObject.model_validate(response.json())
            assert response_obj.status == ResponseStatus.COMPLETED

    # ASSERT - response is completed with output
    assert response_obj.output is not None
    assert len(response_obj.output) == 1
    assert response_obj.output[0].content[0].text == expected_answer


async def test_create_response_with_multiple_messages(
    app: FastAPI,
    client: AsyncClient,
    auth: BasicAuth,
    with_api_server_celery_worker: TestWorkController,
    mocked_chatbot_backend: respx.MockRouter,
):
    # ARRANGE
    mocked_chatbot_backend.post("/v1/chat/completions").respond(
        200,
        json={
            "id": "fake-completion-id",
            "choices": [{"index": 0, "message": {"content": "4"}}],
        },
    )

    body = {
        "background": True,
        "input": [
            {"role": "developer", "content": "You are a helpful assistant."},
            {"role": "user", "content": "What is 2+2?"},
        ],
        "model": _CHAT_MODEL,
        "temperature": 0.5,
    }

    # ACT
    response = await client.post(
        f"/{API_VTAG}/responses",
        auth=auth,
        json=body,
    )

    # ASSERT
    assert response.status_code == status.HTTP_200_OK
    response_obj = ResponseObject.model_validate(response.json())
    assert response_obj.status == ResponseStatus.QUEUED
    response_id = response_obj.id

    # Poll GET /responses/{id} until completed
    async for attempt in AsyncRetrying(
        stop=stop_after_delay(30),
        wait=wait_fixed(wait=datetime.timedelta(seconds=1.0)),
        reraise=True,
        retry=retry_if_exception_type(AssertionError),
    ):
        with attempt:
            response = await client.get(
                f"/{API_VTAG}/responses/{response_id}",
                auth=auth,
            )
            if response.status_code != status.HTTP_200_OK:
                pytest.fail(f"GET /responses/{response_id} failed with {response.status_code}")
            response_obj = ResponseObject.model_validate(response.json())
            assert response_obj.status == ResponseStatus.COMPLETED

    assert response_obj.output is not None
    assert response_obj.output[0].content[0].text == "4"


async def test_create_response_task_failure_is_reported(
    app: FastAPI,
    client: AsyncClient,
    auth: BasicAuth,
    with_api_server_celery_worker: TestWorkController,
    mocked_chatbot_backend: respx.MockRouter,
):
    # ARRANGE - chatbot is unreachable
    mocked_chatbot_backend.post("/v1/chat/completions").mock(side_effect=ConnectionError("Chatbot service unavailable"))

    body = {
        "background": True,
        "input": [
            {"role": "user", "content": "Hello"},
        ],
        "model": _CHAT_MODEL,
        "temperature": 1.0,
    }

    # ACT - submit the task
    response = await client.post(
        f"/{API_VTAG}/responses",
        auth=auth,
        json=body,
    )
    assert response.status_code == status.HTTP_200_OK
    response_obj = ResponseObject.model_validate(response.json())
    response_id = response_obj.id

    # ACT - poll GET /responses/{id} until no longer in progress
    async for attempt in AsyncRetrying(
        stop=stop_after_delay(30),
        wait=wait_fixed(wait=datetime.timedelta(seconds=1.0)),
        reraise=True,
        retry=retry_if_exception_type(AssertionError),
    ):
        with attempt:
            response = await client.get(
                f"/{API_VTAG}/responses/{response_id}",
                auth=auth,
            )
            if response.status_code != status.HTTP_200_OK:
                pytest.fail(f"GET /responses/{response_id} failed with {response.status_code}")
            response_obj = ResponseObject.model_validate(response.json())
            assert response_obj.status not in (ResponseStatus.QUEUED, ResponseStatus.IN_PROGRESS)

    # ASSERT - task failure is reported
    assert response_obj.status == ResponseStatus.FAILED
    assert response_obj.error is not None


async def test_get_nonexistent_response_returns_404(
    app: FastAPI,
    client: AsyncClient,
    auth: BasicAuth,
    with_api_server_celery_worker: TestWorkController,
):
    # ACT - request a response that was never created
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = await client.get(
        f"/{API_VTAG}/responses/{fake_id}",
        auth=auth,
    )

    # ASSERT
    assert response.status_code == status.HTTP_404_NOT_FOUND
