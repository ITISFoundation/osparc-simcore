# pylint: disable=redefined-outer-name

import asyncio

import pytest
from aiohttp import web
from fastapi import FastAPI
from simcore_service_dynamic_sidecar.modules.health_check import (
    AppType,
    HealthCheckHandler,
    HealthReport,
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
    "handlers, expected_health_report",
    [
        ([], HealthReport(is_healthy=True, ok_checks=[], failing_checks=[])),
        (
            [
                health_ok,
            ],
            HealthReport(
                is_healthy=True, ok_checks=[health_ok.__name__], failing_checks=[]
            ),
        ),
        (
            [
                health_ok,
                health_takes_too_long,
            ],
            HealthReport(
                is_healthy=False,
                ok_checks=[health_ok.__name__],
                failing_checks=[health_takes_too_long.__name__],
            ),
        ),
        (
            [
                health_ok,
                health_raises_error,
            ],
            HealthReport(
                is_healthy=False,
                ok_checks=[health_ok.__name__],
                failing_checks=[health_raises_error.__name__],
            ),
        ),
        (
            [
                health_ok,
                health_takes_too_long,
                health_raises_error,
            ],
            HealthReport(
                is_healthy=False,
                ok_checks=[health_ok.__name__],
                failing_checks=[
                    health_takes_too_long.__name__,
                    health_raises_error.__name__,
                ],
            ),
        ),
    ],
)
async def test_health_check_workflow(
    app: FastAPI,
    handlers: list[HealthCheckHandler],
    expected_health_report: HealthReport,
):
    setup_health_check(app)

    for handler in handlers:
        register(app, handler)

    health_report = await is_healthy(app)
    assert health_report == expected_health_report


async def test_health_check_wrong_app_type():
    with pytest.raises(UnsupportedApplicationTypeError):
        setup_health_check(object())  # type: ignore

    with pytest.raises(UnsupportedApplicationTypeError):
        register(object(), health_ok)  # type: ignore

    with pytest.raises(UnsupportedApplicationTypeError):
        await is_healthy(object())  # type: ignore
