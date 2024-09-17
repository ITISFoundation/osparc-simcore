# pylint: disable=all


from collections.abc import Callable
from typing import Any

import pytest
from fastapi import FastAPI
from pydantic import ValidationError
from servicelib.fastapi.tracing import setup_tracing
from settings_library.tracing import TracingSettings


@pytest.fixture
def mocked_app() -> FastAPI:
    return FastAPI(title="opentelemetry example")


@pytest.fixture
def tracing_settings_in(request: pytest.FixtureRequest) -> dict[str, Any]:
    return request.param


@pytest.fixture()
def set_and_clean_settings_env_vars(
    monkeypatch: pytest.MonkeyPatch, tracing_settings_in: Callable[[], dict[str, Any]]
) -> None:
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
        ("http://opentelemetry-collector", "4318"),
    ],
    indirect=True,
)
async def test_valid_tracing_settings(
    mocked_app: FastAPI,
    set_and_clean_settings_env_vars: Callable[[], None],
    tracing_settings_in: Callable[[], dict[str, Any]],
):
    tracing_settings = TracingSettings()
    setup_tracing(
        mocked_app,
        tracing_settings=tracing_settings,
        service_name="Mock-Openetlemetry-Pytest",
    )
    # idempotency
    setup_tracing(
        mocked_app,
        tracing_settings=tracing_settings,
        service_name="Mock-Openetlemetry-Pytest",
    )


@pytest.mark.parametrize(
    "tracing_settings_in",
    [
        ("http://opentelemetry-collector", 80),
        ("http://opentelemetry-collector", 1238712936),
        ("opentelemetry-collector", 4318),
        ("httsdasp://ot@##el-collector", 4318),
        (None, "1238712936"),
    ],
    indirect=True,
)
async def test_invalid_tracing_settings(
    mocked_app: FastAPI,
    set_and_clean_settings_env_vars: Callable[[], None],
    tracing_settings_in: Callable[[], dict[str, Any]],
):
    app = mocked_app
    with pytest.raises((BaseException, ValidationError, TypeError)):  # noqa: PT012
        tracing_settings = TracingSettings()
        setup_tracing(
            app,
            tracing_settings=tracing_settings,
            service_name="Mock-Openetlemetry-Pytest",
        )


@pytest.mark.parametrize(
    "tracing_settings_in",  # noqa: PT002
    [("", ""), ("", None), (None, None)],
    indirect=True,
)
async def test_missing_tracing_settings(
    mocked_app: FastAPI,
    set_and_clean_settings_env_vars: Callable[[], None],
    tracing_settings_in: Callable[[], dict[str, Any]],
):
    tracing_settings = TracingSettings()
    setup_tracing(
        mocked_app,
        tracing_settings=tracing_settings,
        service_name="Mock-Openetlemetry-Pytest",
    )


@pytest.mark.parametrize(
    "tracing_settings_in",
    [("http://opentelemetry-collector", None), (None, 4318)],
    indirect=True,
)
async def test_incomplete_tracing_settings(
    set_and_clean_settings_env_vars: Callable[[], None],
    tracing_settings_in: Callable[[], dict[str, Any]],
    mocked_app: FastAPI,
):
    tracing_settings = TracingSettings()
    with pytest.raises(RuntimeError):
        setup_tracing(
            mocked_app,
            tracing_settings=tracing_settings,
            service_name="Mock-Openetlemetry-Pytest",
        )
