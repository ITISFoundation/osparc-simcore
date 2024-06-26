# pylint: disable=logging-fstring-interpolation
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements
# pylint: disable=unnecessary-lambda
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import os
from collections.abc import Iterator
from datetime import datetime, timezone
from http import HTTPStatus

import pytest
from playwright.sync_api import APIRequestContext
from pydantic import AnyUrl
from pytest_simcore.helpers.logging import test_logger
from tenacity import Retrying
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed

NUM_OF_SLEEPERS = os.environ["NUM_OF_SLEEPERS"]
WALLET_ID = os.environ["WALLET_ID"]
STUDY_ID = os.environ["STUDY_ID"]


@pytest.fixture
def stop_pipeline(
    api_request_context: APIRequestContext, product_url: str
) -> Iterator[None]:
    yield

    api_request_context.post(f"{product_url}v0/computations/{STUDY_ID}:stop")


def test_resource_usage_tracker(
    log_in_and_out: None,
    api_request_context: APIRequestContext,
    product_url: AnyUrl,
    stop_pipeline: None,
):
    # 1. Resource usage before
    rut_before = api_request_context.get(
        f"{product_url}v0/services/-/resource-usages?wallet_id={WALLET_ID}&offset=0&limit={NUM_OF_SLEEPERS}"
    )
    assert rut_before.status == HTTPStatus.OK
    service_runs_before = rut_before.json()["data"]
    service_run_ids_before = set()
    for service_run in service_runs_before:
        service_run_ids_before.add(service_run["service_run_id"])
    test_logger.info(f"Service runs before: {service_run_ids_before}")

    # 2. Start computations
    data = {"subgraph": [], "force_restart": True}
    resp = api_request_context.post(
        f"{product_url}v0/computations/{STUDY_ID}:start",
        data=data,
    )
    assert resp.status == HTTPStatus.CREATED

    for attempt in Retrying(
        wait=wait_fixed(60),
        stop=stop_after_delay(1000),
        retry=retry_if_exception_type(AssertionError),
        reraise=True,
    ):
        with attempt:
            test_logger.info(
                f"====================={datetime.now(tz=timezone.utc)}============================="
            )
            output = api_request_context.get(f"{product_url}v0/projects/{STUDY_ID}")
            assert output.status == HTTPStatus.OK
            workbench = output.json()["data"]["workbench"]
            assert len(workbench.keys()) == int(NUM_OF_SLEEPERS)
            status_check = set()
            for node in list(workbench.keys()):
                node_label = workbench[node]["label"]
                node_current_status = workbench[node]["state"]["currentStatus"]
                test_logger.info("%s", (node_label, node_current_status, node))
                status_check.add(node_current_status)

            assert len(status_check.union({"SUCCESS", "FAILED"})) == 2

    # 3. Check Resource usage after
    rut_after = api_request_context.get(
        f"{product_url}v0/services/-/resource-usages?wallet_id={WALLET_ID}&offset=0&limit={NUM_OF_SLEEPERS}"
    )
    assert rut_after.status == HTTPStatus.OK
    service_runs_after = rut_after.json()["data"]
    service_run_ids_after = set()
    for service_run in service_runs_after:
        service_run_ids_after.add(service_run["service_run_id"])
    test_logger.info(f"Service runs after: {service_run_ids_after}")

    # If there is an intersection with old service run id, that means that
    # RUT didn't created a new service run id
    assert service_run_ids_before.intersection(service_run_ids_after) == set()
