# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from collections.abc import Callable

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient
from pydantic import ValidationError
from servicelib.aiohttp.tracing import setup_tracing
from settings_library.tracing import TracingSettings


@pytest.fixture
def tracing_settings_in(request):
    return request.param


@pytest.fixture()
def set_and_clean_settings_env_vars(
    monkeypatch: pytest.MonkeyPatch, tracing_settings_in
):
    if tracing_settings_in[0]:
        monkeypatch.setenv(
            "TRACING_OPENTELEMETRY_COLLECTOR_ENDPOINT", f"{tracing_settings_in[0]}"
        )
    if tracing_settings_in[1]:
        monkeypatch.setenv(
            "TRACING_OPENTELEMETRY_COLLECTOR_PORT", f"{tracing_settings_in[1]}"
        )


@pytest.mark.parametrize(
    "tracing_settings_in",
    [
        ("http://opentelemetry-collector", 4318),
    ],
    indirect=True,
)
async def test_valid_tracing_settings(
    aiohttp_client: Callable,
    set_and_clean_settings_env_vars: Callable,
    tracing_settings_in,
) -> TestClient:
    app = web.Application()
    service_name = "simcore_service_webserver"
    tracing_settings = TracingSettings()
    setup_tracing(
        app,
        service_name=service_name,
        tracing_settings=tracing_settings,
    )


@pytest.mark.parametrize(
    "tracing_settings_in",
    [
        ("http://opentelemetry-collector", 80),
        ("opentelemetry-collector", 4318),
        ("httsdasp://ot@##el-collector", 4318),
    ],
    indirect=True,
)
async def test_invalid_tracing_settings(
    aiohttp_client: Callable,
    set_and_clean_settings_env_vars: Callable,
    tracing_settings_in,
) -> TestClient:
    with pytest.raises(ValidationError):
        TracingSettings()
