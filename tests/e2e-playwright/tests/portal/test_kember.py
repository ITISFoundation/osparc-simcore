# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

"""Port of the legacy tests/e2e/portal/Kember.js Puppeteer script."""

from collections.abc import Callable
from typing import Any

from playwright.sync_api import Page
from pytest_simcore.helpers.playwright import (
    app_mode_trigger_next_app,
    check_node_outputs,
    get_node_id_from_service_key,
)
from pytest_simcore.helpers.playwright_portal import (
    run_pipeline_and_wait_done,
    wait_for_voila_iframe,
    wait_for_voila_rendered,
)


def _get_app_mode_steps(page: Page) -> list[str]:
    """Returns the visible app-mode step button ids. Port of `TutorialBase.getAppModeSteps()`."""
    page.get_by_test_id("appModeButtons").wait_for(state="visible")
    buttons = page.locator('[osparc-test-id="appModeButtons"] > *')
    step_ids = [buttons.nth(i).get_attribute("osparc-test-id") for i in range(buttons.count())]
    return [step_id for step_id in step_ids if step_id and "AppMode_StepBtn" in step_id]


def test_kember(
    page: Page,
    open_study_link: Callable[..., Any],
    anonymous_study_url: str,
    service_start_timeout: int,
) -> None:
    opened_study = open_study_link(anonymous_study_url)
    project_data = opened_study.project_data
    workbench = project_data["workbench"]
    kember_solver_id = get_node_id_from_service_key(workbench, "kember-cardiac-model")
    kember_viewer_id = get_node_id_from_service_key(workbench, "voila-viewer")

    app_mode_steps = _get_app_mode_steps(page)
    assert len(app_mode_steps) == 2, f"Two app-mode steps expected, got {app_mode_steps}"

    # run solver
    run_pipeline_and_wait_done(
        page,
        opened_study.websocket,
        run_button_test_id="AppMode_RunBtn",
        timeout_ms=service_start_timeout,
    )
    check_node_outputs(
        page,
        study_id=project_data["uuid"],
        node_id=kember_solver_id,
        expected_file_names=["logs.zip", "outputController.dat"],
        open_outputs_folder=True,
        app_mode=True,
    )

    # open kember viewer
    app_mode_trigger_next_app(page)
    iframe_locator = wait_for_voila_iframe(page, kember_viewer_id)
    wait_for_voila_rendered(iframe_locator)
