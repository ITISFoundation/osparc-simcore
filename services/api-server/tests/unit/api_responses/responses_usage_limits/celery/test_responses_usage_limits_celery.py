# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name
# pylint: disable=no-name-in-module

"""Chatbox usage limits — background (Celery) path, tested at the HTTP seam.

The API app places the Reservation at submit time; the in-process worker re-checks the
Global Budget Guard at task start and reconciles to the actual usage at task end.
"""

import datetime
import json

import httpx
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
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_delay, wait_fixed

pytest_simcore_core_services_selection = ["postgres", "rabbit"]
pytest_simcore_ops_services_selection = ["adminer"]

# every test needs an empty Usage Ledger and a drained broker queue
pytestmark = pytest.mark.usefixtures("fresh_usage_ledger", "purge_stale_tasks")


async def _wait_for_completion(client: AsyncClient, auth: BasicAuth, response_id: str) -> ResponseObject:
    async for attempt in AsyncRetrying(
        stop=stop_after_delay(30),
        wait=wait_fixed(datetime.timedelta(seconds=0.5)),
        reraise=True,
        retry=retry_if_exception_type(AssertionError),
    ):
        with attempt:
            response = await client.get(f"/{API_VTAG}/responses/{response_id}", auth=auth)
            assert response.status_code == status.HTTP_200_OK
            obj = ResponseObject.model_validate(response.json())
            assert obj.status == ResponseStatus.COMPLETED
            return obj
    raise AssertionError  # unreachable


@pytest.mark.parametrize(
    "app_environment",
    [{"WINDOW_SPEND_USD": 10, "REQUESTS_PER_MINUTE": 100}],
    indirect=True,
)
async def test_celery_completion_debits_window_and_surfaces_usage(
    app: FastAPI,
    client: AsyncClient,
    auth: BasicAuth,
    usage_builders,
    read_ledger_state,
    with_api_server_celery_worker: TestWorkController,
    mocked_chatbot_backend: respx.MockRouter,
):
    # ARRANGE - non-streamed completion reporting 1000 tokens ($0.0025 at 2.5 USD/MTok)
    mocked_chatbot_backend.post("/v1/chat/completions").respond(
        200,
        json={
            "id": "fake-completion-id",
            "choices": [{"index": 0, "message": {"content": "hi"}}],
            "usage": {"prompt_tokens": 400, "completion_tokens": 600, "total_tokens": 1000},
        },
    )

    # ACT - submit (Reservation placed) and wait for the worker to finish
    submit = await client.post(f"/{API_VTAG}/responses", auth=auth, json=usage_builders.make_background_body())
    assert submit.status_code == status.HTTP_200_OK
    obj = _wait_obj(submit)

    completed = await _wait_for_completion(client, auth, obj.id)

    # ASSERT - the completion reports the ACTUAL usage to the client
    assert completed.usage is not None
    assert completed.usage.total_tokens == 1000
    assert completed.usage.prompt_tokens == 400
    assert completed.usage.completion_tokens == 600

    # ASSERT - the worker reconciled: Reservation fully refunded, Spend = actual usage
    state = await read_ledger_state()
    window = next(iter(state["windows"].values()))
    assert window["reservations"] == pytest.approx(0.0)
    assert window["spend"] == pytest.approx(0.0025)
    assert state["global"]["spend"] == pytest.approx(0.0025)
    assert state["global"]["requests"] == 1


@pytest.mark.parametrize(
    "app_environment",
    [{"WINDOW_SPEND_USD": 10, "REQUESTS_PER_MINUTE": 100}],
    indirect=True,
)
async def test_celery_missing_usage_falls_back_to_estimate(
    app: FastAPI,
    client: AsyncClient,
    auth: BasicAuth,
    usage_builders,
    read_ledger_state,
    with_api_server_celery_worker: TestWorkController,
    mocked_chatbot_backend: respx.MockRouter,
):
    # ARRANGE - completion WITHOUT any usage field
    mocked_chatbot_backend.post("/v1/chat/completions").respond(
        200,
        json={
            "id": "fake-completion-id",
            "choices": [{"index": 0, "message": {"content": "the answer"}}],
        },
    )

    # ACT
    submit = await client.post(f"/{API_VTAG}/responses", auth=auth, json=usage_builders.make_background_body())
    assert submit.status_code == status.HTTP_200_OK
    completed = await _wait_for_completion(client, auth, _wait_obj(submit).id)

    # ASSERT - never fails over accounting, and an estimated Spend was debited
    assert completed.usage is None
    state = await read_ledger_state()
    window = next(iter(state["windows"].values()))
    assert window["reservations"] == pytest.approx(0.0)
    assert window["spend"] > 0


@pytest.mark.parametrize(
    "app_environment",
    [{"WINDOW_SPEND_USD": 10, "REQUESTS_PER_MINUTE": 100}],
    indirect=True,
)
async def test_celery_task_failure_releases_reservation(
    app: FastAPI,
    client: AsyncClient,
    auth: BasicAuth,
    usage_builders,
    read_ledger_state,
    with_api_server_celery_worker: TestWorkController,
    mocked_chatbot_backend: respx.MockRouter,
):
    # ARRANGE - the Chatbox fails while the task runs
    mocked_chatbot_backend.post("/v1/chat/completions").respond(500, json={"detail": "boom"})

    # ACT
    submit = await client.post(f"/{API_VTAG}/responses", auth=auth, json=usage_builders.make_background_body())
    assert submit.status_code == status.HTTP_200_OK
    response_id = _wait_obj(submit).id

    # the task ends FAILED: wait for a terminal state (delivery/execution may take a
    # few seconds with the in-memory broker)
    obj = None
    async for attempt in AsyncRetrying(
        stop=stop_after_delay(30),
        wait=wait_fixed(datetime.timedelta(seconds=0.5)),
        reraise=True,
        retry=retry_if_exception_type(AssertionError),
    ):
        with attempt:
            response = await client.get(f"/{API_VTAG}/responses/{response_id}", auth=auth)
            assert response.status_code == status.HTTP_200_OK
            obj = ResponseObject.model_validate(response.json())
            assert obj.status not in (ResponseStatus.QUEUED, ResponseStatus.IN_PROGRESS)

    # ASSERT - the failed task must not leave any Spend behind and must refund its
    # Reservation entirely
    assert obj is not None
    assert obj.status == ResponseStatus.FAILED
    state = await read_ledger_state()
    assert state["global"].get("spend", 0.0) == pytest.approx(0.0)
    assert state["global"].get("requests", 0.0) == 0
    if state["windows"]:
        window = next(iter(state["windows"].values()))
        # release() only ever touches "reservations": a failed task never adds Spend,
        # and its cold-start Reservation must be fully refunded
        assert window.get("spend", 0.0) == pytest.approx(0.0)
        assert window.get("reservations", 0.0) == pytest.approx(0.0)


@pytest.mark.parametrize(
    "app_environment",
    [{"WINDOW_SPEND_USD": 0.003, "REQUESTS_PER_MINUTE": 100}],
    indirect=True,
)
async def test_celery_window_quota_exhausted_rejects_at_submit(
    client: AsyncClient,
    auth: BasicAuth,
    usage_builders,
    with_api_server_celery_worker: TestWorkController,
    mocked_chatbot_backend: respx.MockRouter,
):
    # ARRANGE - cold start: a single Reservation covers the whole $0.003 window, so a
    # second submit cannot fit while the first is still in flight or already spent.
    mocked_chatbot_backend.post("/v1/chat/completions").respond(
        200,
        json={
            "id": "fake-completion-id",
            "choices": [{"index": 0, "message": {"content": "hi"}}],
            "usage": {"prompt_tokens": 400, "completion_tokens": 600, "total_tokens": 1000},
        },
    )
    first = await client.post(f"/{API_VTAG}/responses", auth=auth, json=usage_builders.make_background_body())
    assert first.status_code == status.HTTP_200_OK
    await _wait_for_completion(client, auth, _wait_obj(first).id)

    # ACT
    second = await client.post(f"/{API_VTAG}/responses", auth=auth, json=usage_builders.make_background_body())

    # ASSERT - rejected at submit, before any queueing
    assert second.status_code == status.HTTP_403_FORBIDDEN
    assert "chatbot_window_quota_exceeded" in json.dumps(second.json()["errors"])


def _wait_obj(submit_response: httpx.Response) -> ResponseObject:
    obj = ResponseObject.model_validate(submit_response.json())
    assert obj.status == ResponseStatus.QUEUED
    return obj
