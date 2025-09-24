# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument

from helpers import assert_contains_text
from playwright.async_api import Page
from simcore_service_dynamic_scheduler.api.frontend._utils import get_settings

pytest_simcore_core_services_selection = [
    "postgres",
    "rabbit",
    "redis",
]

pytest_simcore_ops_services_selection = [
    "redis-commander",
]


async def test_placeholder_index(
    app_runner: None, async_page: Page, server_host_port: str
):
    await async_page.goto(
        f"{server_host_port}{get_settings().DYNAMIC_SCHEDULER_UI_MOUNT_PATH}"
    )

    await assert_contains_text(async_page, "PLACEHOLDER for internal scheduler UI")
