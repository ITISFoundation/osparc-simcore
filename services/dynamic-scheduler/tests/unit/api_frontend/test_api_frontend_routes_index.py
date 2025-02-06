# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument

from collections.abc import Callable
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from helpers import (
    assert_contains_text,
    assert_not_contains_text,
    click_on_text,
    get_legacy_service_status,
    get_new_style_service_status,
    take_screenshot_on_error,
)
from models_library.api_schemas_directorv2.dynamic_services import DynamicServiceGet
from models_library.api_schemas_dynamic_scheduler.dynamic_services import (
    DynamicServiceStart,
    DynamicServiceStop,
)
from models_library.api_schemas_webserver.projects_nodes import NodeGet
from models_library.projects_nodes_io import NodeID
from playwright.async_api import Page
from simcore_service_dynamic_scheduler.api.frontend._utils import get_settings
from simcore_service_dynamic_scheduler.services.service_tracker import (
    set_if_status_changed_for_service,
    set_request_as_running,
    set_request_as_stopped,
)
from tenacity import AsyncRetrying, stop_after_delay, wait_fixed

pytest_simcore_core_services_selection = [
    "postgres",
    "rabbit",
    "redis",
]

pytest_simcore_ops_services_selection = [
    # "redis-commander",
]


async def test_index_with_elements(
    app_runner: None,
    async_page: Page,
    server_host_port: str,
    not_initialized_app: FastAPI,
    get_dynamic_service_start: Callable[[NodeID], DynamicServiceStart],
    get_dynamic_service_stop: Callable[[NodeID], DynamicServiceStop],
):
    await async_page.goto(
        f"{server_host_port}{get_settings().DYNAMIC_SCHEDULER_UI_MOUNT_PATH}"
    )

    # 1. no content
    await assert_contains_text(async_page, "Total tracked services:")
    await assert_contains_text(async_page, "0")
    await assert_not_contains_text(async_page, "Details")

    # 2. add elements and check
    await set_request_as_running(
        not_initialized_app, get_dynamic_service_start(uuid4())
    )
    await set_request_as_stopped(not_initialized_app, get_dynamic_service_stop(uuid4()))

    await assert_contains_text(async_page, "2")
    await assert_contains_text(async_page, "Details", instances=2)


@pytest.mark.parametrize(
    "service_status",
    [
        get_new_style_service_status("running"),
        get_legacy_service_status("running"),
    ],
)
async def test_main_page(
    app_runner: None,
    async_page: Page,
    server_host_port: str,
    node_id: NodeID,
    service_status: NodeGet | DynamicServiceGet,
    not_initialized_app: FastAPI,
    get_dynamic_service_start: Callable[[NodeID], DynamicServiceStart],
    mock_stop_dynamic_service: AsyncMock,
):
    await async_page.goto(
        f"{server_host_port}{get_settings().DYNAMIC_SCHEDULER_UI_MOUNT_PATH}"
    )

    # 1. no content
    await assert_contains_text(async_page, "Total tracked services:")
    await assert_contains_text(async_page, "0")
    await assert_not_contains_text(async_page, "Details")

    # 2. start a service shows content
    await set_request_as_running(
        not_initialized_app, get_dynamic_service_start(node_id)
    )
    await set_if_status_changed_for_service(
        not_initialized_app, node_id, service_status
    )

    await assert_contains_text(async_page, "1")
    await assert_contains_text(async_page, "Details")

    # 3. click on stop and then cancel
    await click_on_text(async_page, "Stop Service")
    await assert_contains_text(
        async_page, "The service will be stopped and its data will be saved"
    )
    await click_on_text(async_page, "Cancel")

    # 4. click on stop then confirm

    await assert_not_contains_text(
        async_page, "The service will be stopped and its data will be saved"
    )
    await click_on_text(async_page, "Stop Service")
    await assert_contains_text(
        async_page, "The service will be stopped and its data will be saved"
    )

    mock_stop_dynamic_service.assert_not_awaited()
    await click_on_text(async_page, "Stop Now")

    async with take_screenshot_on_error(async_page):
        async for attempt in AsyncRetrying(
            reraise=True, wait=wait_fixed(0.1), stop=stop_after_delay(3)
        ):
            with attempt:
                mock_stop_dynamic_service.assert_awaited_once()
