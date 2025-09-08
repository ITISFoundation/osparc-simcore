import logging
import re
from collections.abc import Callable
from typing import Any, Final

from playwright.sync_api import Page
from pydantic import AnyUrl
from pytest_simcore.helpers.logging_tools import log_context
from pytest_simcore.helpers.playwright import (
    MINUTE,
    RobustWebSocket,
    ServiceType,
    wait_for_service_running,
)

_WAITING_FOR_SERVICE_TO_START: Final[int] = 5 * MINUTE
_DEFAULT_RESPONSE_TO_WAIT_FOR: Final[re.Pattern] = re.compile(
    r"/flask/list_function_job_collections_for_functionid"
)


def test_response_surface_modeling(
    page: Page,
    create_project_from_service_dashboard: Callable[
        [ServiceType, str, str | None, str | None], dict[str, Any]
    ],
    log_in_and_out: RobustWebSocket,
    service_key: str,
    service_version: str | None,
    product_url: AnyUrl,
    is_service_legacy: bool,
):
    with (
        log_context(
            logging.INFO,
            f"Waiting for {service_key} to be responsive (waiting for {_DEFAULT_RESPONSE_TO_WAIT_FOR})",
        ),
        page.expect_response(
            _DEFAULT_RESPONSE_TO_WAIT_FOR, timeout=_WAITING_FOR_SERVICE_TO_START
        ),
    ):
        project_data = create_project_from_service_dashboard(
            ServiceType.DYNAMIC, service_key, None, service_version
        )
        assert "workbench" in project_data, "Expected workbench to be in project data!"
        assert isinstance(
            project_data["workbench"], dict
        ), "Expected workbench to be a dict!"
        node_ids: list[str] = list(project_data["workbench"])
        assert len(node_ids) == 1, "Expected 1 node in the workbench!"

        wait_for_service_running(
            page=page,
            node_id=node_ids[0],
            websocket=log_in_and_out,
            timeout=_WAITING_FOR_SERVICE_TO_START,
            press_start_button=False,
            product_url=product_url,
            is_service_legacy=is_service_legacy,
        )
