# pylint: disable=logging-fstring-interpolation
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements
# pylint: disable=unnecessary-lambda
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import logging
import re
from typing import Any, Callable, Final

from playwright.sync_api import Page, WebSocket
from pytest_simcore.helpers.logging_tools import log_context
from pytest_simcore.helpers.playwright import (
    MINUTE,
    ServiceType,
    wait_for_service_running,
)

projects_uuid_pattern: Final[re.Pattern] = re.compile(
    r"/projects/([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})"
)
_EC2_STARTUP_MAX_WAIT_TIME: Final[int] = 1 * MINUTE
_S4L_MAX_STARTUP_TIME: Final[int] = 1 * MINUTE
_S4L_DOCKER_PULLING_MAX_TIME: Final[int] = 10 * MINUTE
_S4L_AUTOSCALED_MAX_STARTUP_TIME: Final[int] = (
    _EC2_STARTUP_MAX_WAIT_TIME + _S4L_DOCKER_PULLING_MAX_TIME + _S4L_MAX_STARTUP_TIME
)


def test_sim4life(
    page: Page,
    create_project_from_service_dashboard: Callable[
        [ServiceType, str, str | None], dict[str, Any]
    ],
    log_in_and_out: WebSocket,
    service_key: str,
    autoscaled: bool,
    check_videostreaming: bool,
):
    project_data = create_project_from_service_dashboard(
        ServiceType.DYNAMIC, service_key, None
    )
    assert "workbench" in project_data, "Expected workbench to be in project data!"
    assert isinstance(
        project_data["workbench"], dict
    ), "Expected workbench to be a dict!"
    node_ids: list[str] = list(project_data["workbench"])
    assert len(node_ids) == 1, "Expected 1 node in the workbench!"

    with log_context(logging.INFO, "launch S4l"):
        s4l_iframe = wait_for_service_running(
            page=page,
            node_id=node_ids[0],
            websocket=log_in_and_out,
            timeout=(
                _S4L_AUTOSCALED_MAX_STARTUP_TIME
                if autoscaled
                else _S4L_MAX_STARTUP_TIME
            ),
            press_start_button=False,
        )

    # NOTE: here the startup screen is up there. from the test it seems the default timeout is enough.
    # Wait until grid is shown
    with log_context(logging.INFO, "Interact with S4l"):
        s4l_iframe.get_by_test_id("tree-item-Grid").nth(0).click()
        page.wait_for_timeout(30000)
        s4l_iframe.get_by_role("img", name="Remote render").click(button="right")

    if check_videostreaming:
        with log_context(logging.INFO, "Check videostreaming works"):
            raise NotImplementedError(
                "TODO: currently I was not able to make playwright browser show any videostreaming"
            )
