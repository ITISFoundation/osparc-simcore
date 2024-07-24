# pylint: disable=logging-fstring-interpolation
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements
# pylint: disable=unnecessary-lambda
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import re
from typing import Any, Callable, Final

from playwright.sync_api import Page
from pytest_simcore.helpers.playwright import ServiceType

projects_uuid_pattern: Final[re.Pattern] = re.compile(
    r"/projects/([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})"
)


def test_sim4life(
    page: Page,
    create_project_from_service_dashboard: Callable[
        [ServiceType, str, str | None], dict[str, Any]
    ],
    service_key: str,
):
    create_project_from_service_dashboard(ServiceType.DYNAMIC, service_key, None)

    # Wait until grid is shown
    page.frame_locator(".qx-main-dark").get_by_role("img", name="Remote render").click(
        button="right", timeout=600000
    )
    page.wait_for_timeout(1000)
