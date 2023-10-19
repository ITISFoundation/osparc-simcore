# pylint: disable=redefined-outer-name

import asyncio

import pytest
from aiohttp import web
from fastapi import FastAPI
from simcore_service_dynamic_sidecar.modules import healthcheck


@pytest.fixture(params=[FastAPI(), web.Application()])
def app(request: pytest.FixtureRequest) -> healthcheck.AppType:
    return request.param


async def health_ok(_: healthcheck.AppType) -> None:
    ...


async def health_takes_too_long(_: healthcheck.AppType) -> None:
    await asyncio.sleep(2)


async def health_raises_error(_: healthcheck.AppType) -> None:
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
async def test_workflow(
    app: FastAPI, handlers: list[healthcheck.HealthCheckHandler], expected_health: bool
):
    healthcheck.setup(app)

    for handler in handlers:
        healthcheck.register(app, handler)

    assert await healthcheck.is_healthy(app) is expected_health
