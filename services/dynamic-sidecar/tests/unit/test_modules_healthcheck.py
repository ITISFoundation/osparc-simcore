# pylint: disable=redefined-outer-name

import asyncio

import pytest
from aiohttp import web
from fastapi import FastAPI
from simcore_service_dynamic_sidecar.modules.health_check import (
    AppType,
    HealthCheckHandler,
    UnsupportedApplicationTypeError,
    is_healthy,
    register,
    setup_health_check,
)


@pytest.fixture(params=[FastAPI(), web.Application()])
def app(request: pytest.FixtureRequest) -> AppType:
    return request.param


async def health_ok(_: AppType) -> None:
    ...


async def health_takes_too_long(_: AppType) -> None:
    await asyncio.sleep(2)


async def health_raises_error(_: AppType) -> None:
    msg = "raised_as_expected"
    raise RuntimeError(msg)


@pytest.mark.parametrize(
    "handlers, expected_health",
    [
        ([], True),
        (
            [
                health_ok,
            ],
            True,
        ),
        (
            [
                health_ok,
                health_takes_too_long,
            ],
            False,
        ),
        (
            [
                health_ok,
                health_raises_error,
            ],
            False,
        ),
        (
            [
                health_ok,
                health_takes_too_long,
                health_raises_error,
            ],
            False,
        ),
    ],
)
async def test_health_check_workflow(
    app: FastAPI, handlers: list[HealthCheckHandler], expected_health: bool
):
    setup_health_check(app)

    for handler in handlers:
        register(app, handler)

    assert await is_healthy(app) is expected_health


async def test_health_check_wrong_app_type():
    with pytest.raises(UnsupportedApplicationTypeError):
        setup_health_check(object())  # type: ignore

    with pytest.raises(UnsupportedApplicationTypeError):
        register(object(), health_ok)  # type: ignore

    with pytest.raises(UnsupportedApplicationTypeError):
        await is_healthy(object())  # type: ignore
