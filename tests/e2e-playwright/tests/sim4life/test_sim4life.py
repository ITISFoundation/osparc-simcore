# pylint: disable=logging-fstring-interpolation
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements
# pylint: disable=unnecessary-lambda
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import logging
import re
from collections.abc import Callable
from typing import Any, Final

from playwright.sync_api import Page, WebSocket
from pytest_simcore.helpers.logging_tools import log_context
from pytest_simcore.helpers.playwright import (
    MINUTE,
    SECOND,
    ServiceType,
    wait_for_service_running,
)
from pytest_simcore.helpers.playwright_sim4life import (
    S4LWaitForWebsocket,
    check_video_streaming,
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

_S4L_STARTUP_SCREEN_MAX_TIME: Final[int] = 45 * SECOND


def test_sim4life(
    page: Page,
    create_project_from_service_dashboard: Callable[
        [ServiceType, str, str | None], dict[str, Any]
    ],
    create_project_from_new_button: Callable[[str], dict[str, Any]],
    log_in_and_out: WebSocket,
    service_key: str,
    use_plus_button: bool,
    autoscaled: bool,
    check_videostreaming: bool,
):
    if use_plus_button:
        project_data = create_project_from_new_button(service_key)
    else:
        project_data = create_project_from_service_dashboard(
            ServiceType.DYNAMIC, service_key, None
        )
    assert "workbench" in project_data, "Expected workbench to be in project data!"
    assert isinstance(
        project_data["workbench"], dict
    ), "Expected workbench to be a dict!"
    node_ids: list[str] = list(project_data["workbench"])
    assert len(node_ids) == 1, "Expected 1 node in the workbench!"

    with log_context(logging.INFO, "launch S4L") as ctx:
        predicate = S4LWaitForWebsocket(logger=ctx.logger)
        with page.expect_websocket(
            predicate,
            timeout=_S4L_STARTUP_SCREEN_MAX_TIME
            + (
                _S4L_AUTOSCALED_MAX_STARTUP_TIME
                if autoscaled
                else _S4L_MAX_STARTUP_TIME
            )
            + 10 * SECOND,
        ) as ws_info:
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
        s4l_websocket = ws_info.value
        ctx.logger.info("acquired S4L websocket!")

    # Wait until grid is shown
    # NOTE: the startup screen should disappear very fast after the websocket was acquired
    with log_context(logging.INFO, "Interact with S4l"):
        s4l_iframe.get_by_test_id("tree-item-Grid").nth(0).click()
    page.wait_for_timeout(3000)

    if check_videostreaming:
        check_video_streaming(page, s4l_iframe, s4l_websocket)
