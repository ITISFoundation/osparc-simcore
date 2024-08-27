# pylint: disable=logging-fstring-interpolation
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements
# pylint: disable=unnecessary-lambda
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from collections.abc import Callable
from typing import Any

from playwright.sync_api import Page, WebSocket
from pytest_simcore.helpers.playwright import ServiceType
from pytest_simcore.helpers.playwright_sim4life import (
    launch_S4L,
    interact_with_S4L,
    check_video_streaming,
)


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

    resp = launch_S4L(page, node_ids[0], log_in_and_out, autoscaled)
    s4l_websocket = resp["websocket"]
    s4l_iframe = resp["iframe"]
    interact_with_S4L(page, s4l_iframe)

    if check_videostreaming:
        check_video_streaming(page, s4l_iframe, s4l_websocket)
