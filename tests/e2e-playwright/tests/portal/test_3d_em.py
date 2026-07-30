# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

"""Port of the legacy tests/e2e/portal/3D_EM.js Puppeteer script."""

from collections.abc import Callable
from typing import Any

from playwright.sync_api import Page, expect
from pytest_simcore.helpers.playwright import get_node_id_from_service_key, wait_for_service_running

# NOTE: port of the legacy 3D_EM.js, which calls `waitForServices(..., waitForConnected=false)`
_IS_SERVICE_LEGACY = False

_EXPECTED_ENTITIES: list[str] = [
    "EM_02mm.vtk",
    "CellDatatoPointData1",
]


def test_3d_em(
    page: Page,
    open_study_link: Callable[..., Any],
    anonymous_study_url: str,
    service_start_timeout: int,
) -> None:
    opened_study = open_study_link(anonymous_study_url)
    workbench = opened_study.project_data["workbench"]
    node_id = get_node_id_from_service_key(workbench, "3d-viewer-gpu")

    iframe_locator = wait_for_service_running(
        page=page,
        node_id=node_id,
        websocket=opened_study.websocket,
        timeout=service_start_timeout,
        press_start_button=False,
        product_url=opened_study.product_url,
        is_service_legacy=_IS_SERVICE_LEGACY,
    )

    for entity_name in _EXPECTED_ENTITIES:
        expect(iframe_locator.get_by_text(entity_name).first).to_be_visible(timeout=30 * 1000)
