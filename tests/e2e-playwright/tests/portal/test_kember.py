# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument


import logging
from collections.abc import Callable
from typing import Any, Final

from playwright.sync_api import Page
from pytest_simcore.helpers.logging_tools import (
    log_context,
)
from pytest_simcore.helpers.playwright import (
    SECOND,
    app_mode_trigger_next_app,
    check_node_outputs,
    get_node_id_from_service_key,
    run_pipeline_and_wait_done,
)


def _get_app_mode_steps(page: Page) -> list[str]:
    """Returns the visible app-mode step button ids. Port of `TutorialBase.getAppModeSteps()`."""
    page.get_by_test_id("appModeButtons").wait_for(state="visible")
    buttons = page.locator('[osparc-test-id="appModeButtons"] > *')
    step_ids = [buttons.nth(i).get_attribute("osparc-test-id") for i in range(buttons.count())]
    return [step_id for step_id in step_ids if step_id and "AppMode_StepBtn" in step_id]


_IFRAME_MAX_WAIT_TIME: Final[int] = 4 * 60 * SECOND
_RENDERED_MAX_WAIT_TIME: Final[int] = 2 * 60 * SECOND


def test_kember(
    page: Page,
    open_study_link: Callable[..., Any],
    anonymous_study_url: str,
    run_pipeline_timeout: int,
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
        timeout_ms=run_pipeline_timeout,
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
    iframe_locator = page.frame_locator(f'[osparc-test-id="iframe_{kember_viewer_id}"]')
    with log_context(logging.INFO, f"Waiting for iframe of node {kember_viewer_id=}"):
        page.locator(f'[osparc-test-id="iframe_{kember_viewer_id}"]').wait_for(
            state="attached", timeout=_IFRAME_MAX_WAIT_TIME
        )

    with log_context(logging.INFO, "Waiting to render"):
        iframe_locator.locator("#rendered_cells").wait_for(state="visible", timeout=_RENDERED_MAX_WAIT_TIME)
