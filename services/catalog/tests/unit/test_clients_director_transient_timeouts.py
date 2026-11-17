# pylint: disable=not-context-manager
# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
"""Draft tests: catalog behavior while director stalls (disk-full incident 2026-11-17).

While a worker disk was full, director stalled and the catalog background sync
`_ensure_registry_and_database_are_synced` hit `httpx2.ReadTimeout` on
`GET /services` on every tick from ~09:00 to ~11:00 UTC. Each tick logged an
ERROR pair from `clients/director.py::request_wrapper` and raised a 503.
User-facing requests that need the live services map got that 503 too.

The xfail test encodes the proposed behavior (ticket P3 in the tracker): a
transient director timeout during background sync is a WARNING, not ERROR spam.
"""

import logging

import httpx2
import pytest
import respx
from fastapi import FastAPI, HTTPException, status
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from simcore_service_catalog.api._dependencies.director import get_director_client
from simcore_service_catalog.clients.director import DirectorClient


@pytest.fixture
def app_environment(monkeypatch: pytest.MonkeyPatch, app_environment: EnvVarsDict) -> EnvVarsDict:
    return setenvs_from_dict(
        monkeypatch,
        {
            **app_environment,
            "SC_BOOT_MODE": "local-development",
            # keep the director requests fast (same as test_clients_director.py)
            "HTTP_CLIENT_REQUEST_TOTAL_TIMEOUT": "3",
        },
    )


async def test_get_services_map_read_timeout_maps_to_503(
    mocked_director_rest_api_base: respx.MockRouter,
    repository_lifespan_disabled: None,
    background_task_lifespan_disabled: None,
    rabbitmq_and_rpc_setup_disabled: None,
    app: FastAPI,
) -> None:
    # Pins current behavior: any transport failure becomes a 503
    mocked_director_rest_api_base.get("/services").mock(side_effect=httpx2.ReadTimeout("read timed out"))

    director_api = get_director_client(app)
    assert isinstance(director_api, DirectorClient)

    with pytest.raises(HTTPException) as excinfo:
        await director_api.get("/services")

    assert excinfo.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE


@pytest.mark.xfail(
    strict=False,
    reason="spec (P3): director blips during background sync are transient and "
    "must be logged at WARNING (with backoff), not as an ERROR pair every tick",
)
async def test_transient_director_timeout_logs_warning_not_error(
    mocked_director_rest_api_base: respx.MockRouter,
    repository_lifespan_disabled: None,
    background_task_lifespan_disabled: None,
    rabbitmq_and_rpc_setup_disabled: None,
    caplog: pytest.LogCaptureFixture,
    app: FastAPI,
) -> None:
    mocked_director_rest_api_base.get("/services").mock(side_effect=httpx2.ReadTimeout("read timed out"))

    director_api = get_director_client(app)
    with pytest.raises(HTTPException):
        await director_api.get("/services")

    error_records = [r for r in caplog.records if r.levelno >= logging.ERROR]
    assert not error_records, "expected a WARNING for a transient timeout"
