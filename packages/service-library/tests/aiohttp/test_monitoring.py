# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from collections.abc import Callable
from typing import Any

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient
from faker import Faker
from prometheus_client.openmetrics.parser import text_string_to_metric_families
from servicelib.aiohttp import status
from servicelib.aiohttp.monitoring import setup_monitoring
from servicelib.common_headers import (
    UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE,
    X_SIMCORE_USER_AGENT,
)


@pytest.fixture
async def client(
    aiohttp_client: Callable,
    unused_tcp_port_factory: Callable,
) -> TestClient:
    ports = [unused_tcp_port_factory() for _ in range(2)]

    async def monitored_request(request: web.Request) -> web.Response:
        return web.json_response(data={"data": "OK"})

    app = web.Application()
    app.add_routes([web.get("/monitored_request", monitored_request)])

    print("Resources:")
    for resource in app.router.resources():
        print(resource)

    setup_monitoring(app, app_name="pytest_app")

    return await aiohttp_client(app, server_kwargs={"port": ports[0]})


def _assert_metrics_contain_entry(
    metrics_as_text: str,
    metric_name: str,
    sample_name: str,
    labels: dict[str, str],
    value: Any,
) -> None:
    for metric_family in filter(
        lambda family: family.name == metric_name,
        text_string_to_metric_families(metrics_as_text),
    ):
        assert len(metric_family.samples) > 0
        # NOTE: there might be any number of samples
        filtered_samples = list(
            filter(
                lambda sample: sample.name == sample_name and sample.labels == labels,
                metric_family.samples,
            )
        )
        assert len(filtered_samples) == 1
        sample = filtered_samples[0]
        assert sample.value == value
        print(f"Found {metric_name=} with expected {value=}")
        return

    assert False, f"Could not find metric with {metric_name=}"


async def test_setup_monitoring(client: TestClient):
    NUM_CALLS = 12
    for _ in range(NUM_CALLS):
        response = await client.get("/monitored_request")
        assert response.status == status.HTTP_200_OK
        data = await response.json()
        assert data
        assert "data" in data
        assert data["data"] == "OK"

    response = await client.get("/metrics")
    assert response.status == status.HTTP_200_OK
    # by calling it twice, the metrics endpoint should also be incremented
    response = await client.get("/metrics")
    assert response.status == status.HTTP_200_OK
    metrics_as_text = await response.text()
    _assert_metrics_contain_entry(
        metrics_as_text,
        metric_name="http_requests",
        sample_name="http_requests_total",
        labels={
            "endpoint": "/monitored_request",
            "http_status": "200",
            "method": "GET",
            "simcore_user_agent": UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE,
        },
        value=NUM_CALLS,
    )

    _assert_metrics_contain_entry(
        metrics_as_text,
        metric_name="http_requests",
        sample_name="http_requests_total",
        labels={
            "endpoint": "/metrics",
            "http_status": "200",
            "method": "GET",
            "simcore_user_agent": UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE,
        },
        value=1,
    )


async def test_request_with_simcore_user_agent(client: TestClient, faker: Faker):
    faker_simcore_user_agent = faker.name()
    response = await client.get(
        "/monitored_request",
        headers={X_SIMCORE_USER_AGENT: faker_simcore_user_agent},
    )
    assert response.status == status.HTTP_200_OK

    response = await client.get("/metrics")
    assert response.status == status.HTTP_200_OK
    metrics_as_text = await response.text()
    _assert_metrics_contain_entry(
        metrics_as_text,
        metric_name="http_requests",
        sample_name="http_requests_total",
        labels={
            "endpoint": "/monitored_request",
            "http_status": "200",
            "method": "GET",
            "simcore_user_agent": faker_simcore_user_agent,
        },
        value=1,
    )
