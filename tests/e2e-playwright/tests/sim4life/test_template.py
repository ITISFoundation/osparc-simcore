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
from pytest_simcore.helpers.playwright_sim4life import (
    launch_S4L,
    interact_with_S4L,
    check_video_streaming,
)


def test_template(
    page: Page,
    create_project_from_template_dashboard: Callable[[str], dict[str, Any]],
    log_in_and_out: WebSocket,
    template_id: str,
    autoscaled: bool,
    check_videostreaming: bool,
):
    project_data = create_project_from_template_dashboard(template_id)

    assert "workbench" in project_data, "Expected workbench to be in project data!"
    assert isinstance(
        project_data["workbench"], dict
    ), "Expected workbench to be a dict!"
    node_ids: list[str] = list(project_data["workbench"])
    assert len(node_ids) == 1, "Expected 1 node in the workbench!"

    resp = launch_S4L(page, node_ids[0], log_in_and_out, autoscaled, copy_workspace=True)
    s4l_websocket = resp["websocket"]
    s4l_iframe = resp["iframe"]
    interact_with_S4L(page, s4l_iframe)

    if check_videostreaming:
        check_video_streaming(page, s4l_iframe, s4l_websocket)
