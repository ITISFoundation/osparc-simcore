# pylint: disable=logging-fstring-interpolation
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements
# pylint: disable=unnecessary-lambda
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from collections.abc import Callable
from typing import Any

from playwright.sync_api import Page
from pydantic import AnyUrl
from pytest_simcore.helpers.playwright import RestartableWebSocket, ServiceType
from pytest_simcore.helpers.playwright_sim4life import (
    check_video_streaming,
    interact_with_s4l,
    wait_for_launched_s4l,
)


def test_sim4life(
    page: Page,
    create_project_from_service_dashboard: Callable[
        [ServiceType, str, str | None], dict[str, Any]
    ],
    create_project_from_new_button: Callable[[str], dict[str, Any]],
    log_in_and_out: RestartableWebSocket,
    service_key: str,
    use_plus_button: bool,
    is_autoscaled: bool,
    check_videostreaming: bool,
    product_url: AnyUrl,
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

    resp = wait_for_launched_s4l(
        page,
        node_ids[0],
        log_in_and_out,
        autoscaled=is_autoscaled,
        copy_workspace=False,
        product_url=product_url,
    )
    s4l_websocket = resp["websocket"]
    s4l_iframe = resp["iframe"]
    interact_with_s4l(page, s4l_iframe)

    if check_videostreaming:
        check_video_streaming(page, s4l_iframe, s4l_websocket)
