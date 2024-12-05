# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument

from collections.abc import Callable
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from helpers import (
    assert_contains_text,
    click_on_text,
    get_legacy_service_status,
    get_new_style_service_status,
    take_screenshot_on_error,
)
from models_library.api_schemas_directorv2.dynamic_services import DynamicServiceGet
from models_library.api_schemas_dynamic_scheduler.dynamic_services import (
    DynamicServiceStart,
)
from models_library.api_schemas_webserver.projects_nodes import NodeGet
from models_library.projects_nodes_io import NodeID
from playwright.async_api import Page
from simcore_service_dynamic_scheduler.api.frontend._utils import get_settings
from simcore_service_dynamic_scheduler.services.service_tracker import (
    set_if_status_changed_for_service,
    set_request_as_running,
)
from tenacity import AsyncRetrying, stop_after_delay, wait_fixed

pytest_simcore_core_services_selection = [
    "rabbit",
    "redis",
]

pytest_simcore_ops_services_selection = [
    # "redis-commander",
]


async def test_service_details_no_status_present(
    app_runner: None,
    async_page: Page,
    server_host_port: str,
    node_id: NodeID,
    not_initialized_app: FastAPI,
    get_dynamic_service_start: Callable[[NodeID], DynamicServiceStart],
):
    await set_request_as_running(
        not_initialized_app, get_dynamic_service_start(node_id)
    )

    await async_page.goto(
        f"{server_host_port}{get_settings().DYNAMIC_SCHEDULER_UI_MOUNT_PATH}"
    )

    # 1. one service is tracked
    await assert_contains_text(async_page, "Total tracked services:")
    await assert_contains_text(async_page, "1")
    await assert_contains_text(async_page, "Details", instances=1)

    # 2. open details page
    await click_on_text(async_page, "Details")
    # NOTE: if something is wrong with the page the bottom to remove from tracking
    # will not be present
    await assert_contains_text(async_page, "Remove from tracking", instances=1)


async def test_service_details_renders_friendly_404(
    app_runner: None, async_page: Page, server_host_port: str, node_id: NodeID
):
    # node was not started
    url = f"http://{server_host_port}{get_settings().DYNAMIC_SCHEDULER_UI_MOUNT_PATH}service/{node_id}:details"
    await async_page.goto(f"{url}")
    await assert_contains_text(async_page, "Sorry could not find any details for")


@pytest.mark.parametrize(
    "service_status",
    [
        get_new_style_service_status("running"),
        get_legacy_service_status("running"),
    ],
)
async def test_service_details(
    app_runner: None,
    async_page: Page,
    server_host_port: str,
    node_id: NodeID,
    not_initialized_app: FastAPI,
    get_dynamic_service_start: Callable[[NodeID], DynamicServiceStart],
    mock_remove_tracked_service: AsyncMock,
    service_status: NodeGet | DynamicServiceGet,
):
    await set_request_as_running(
        not_initialized_app, get_dynamic_service_start(node_id)
    )
    await set_request_as_running(
        not_initialized_app, get_dynamic_service_start(node_id)
    )
    await set_if_status_changed_for_service(
        not_initialized_app, node_id, service_status
    )

    await async_page.goto(
        f"{server_host_port}{get_settings().DYNAMIC_SCHEDULER_UI_MOUNT_PATH}"
    )

    # 1. one service is tracked
    await assert_contains_text(async_page, "Total tracked services:")
    await assert_contains_text(async_page, "1")
    await assert_contains_text(async_page, "Details", instances=1)

    # 2. open details page
    await click_on_text(async_page, "Details")

    # 3. click "Remove from tracking" -> cancel
    await click_on_text(async_page, "Remove from tracking")
    await click_on_text(async_page, "Cancel")
    mock_remove_tracked_service.assert_not_awaited()

    # 4. click "Remove from tracking" -> confirm
    await click_on_text(async_page, "Remove from tracking")
    await click_on_text(async_page, "Remove service")
    async with take_screenshot_on_error(async_page):
        async for attempt in AsyncRetrying(
            reraise=True, wait=wait_fixed(0.1), stop=stop_after_delay(3)
        ):
            with attempt:
                mock_remove_tracked_service.assert_awaited_once()
