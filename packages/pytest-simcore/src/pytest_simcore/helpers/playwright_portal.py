"""Helpers shared by the tests/e2e-playwright/tests/portal test suite.

These tests port the legacy Puppeteer scripts in tests/e2e/portal, tests/e2e/portal-files and
tests/e2e/publications, which open a public/portal study without logging in
(see `open_study_link` fixture in tests/e2e-playwright/tests/conftest.py) and interact with the
service(s) it contains.

NOTE: only helpers reused by more than one test live here. Logic specific to a single test
lives in that test's module instead.
"""

import datetime
import logging
import re
from typing import Final

from playwright.sync_api import FrameLocator, Page
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from .logging_tools import log_context
from .playwright import (
    SECOND,
    RobustWebSocket,
    RunningState,
    SocketIOProjectStateUpdatedWaiter,
    SocketIOWaitNodeForOutputs,
    decode_socketio_42_message,
    retrieve_project_state_from_decoded_message,
)

_RUN_PIPELINE_MAX_WAIT_TIME: Final[int] = 60 * SECOND
_VOILA_IFRAME_MAX_WAIT_TIME: Final[int] = 4 * 60 * SECOND
_VOILA_RENDERED_MAX_WAIT_TIME: Final[int] = 2 * 60 * SECOND


def _open_node(page: Page, position: int) -> str:
    """Selects the node at `position` in the workbench tree (left panel) and returns its node id.

    Port of the legacy `auto.openNode()`.
    """
    tree_items = page.locator('[osparc-test-id="nodeTreeItem"]')
    node_ids_and_locators = []
    for index in range(tree_items.count()):
        item = tree_items.nth(index)
        node_key = item.get_attribute("osparc-test-key")
        if node_key and node_key != "root":
            node_ids_and_locators.append((node_key, item))

    node_id, locator = node_ids_and_locators[position]
    locator.click()
    # Iframes get loaded on demand
    page.wait_for_timeout(5 * SECOND)
    return node_id


def restore_iframe(page: Page) -> None:
    """Restores a maximized/fullscreen iframe. Port of the legacy `auto.restoreIFrame()`."""
    page.get_by_test_id("restoreBtn").click()


def check_node_outputs(
    page: Page,
    *,
    websocket: RobustWebSocket,
    study_id: str,
    node_position: int | None = None,
    node_id: str | None = None,
    expected_file_names: list[str],
    open_outputs_folder: bool = False,
    app_mode: bool = False,
    outputs_ready_timeout_ms: int = 60 * SECOND,
) -> None:
    """Opens a node's output files panel and asserts the number of files it contains.

    Port of the legacy `TutorialBase.checkNodeOutputs()` /
    `TutorialBase.checkNodeOutputsAppMode()`.
    """
    if node_id is None:
        assert node_position is not None, "either node_id or node_position must be provided"
        node_id = _open_node(page, node_position)

    with log_context(
        logging.INFO,
        f"Waiting for node {node_id=} to produce {len(expected_file_names)} output(s)",
    ):
        waiter = SocketIOWaitNodeForOutputs(expected_number_of_outputs=len(expected_file_names), node_id=node_id)
        try:
            with websocket.expect_event("framereceived", waiter, timeout=outputs_ready_timeout_ms):
                pass
        except (PlaywrightTimeoutError, TimeoutError):
            # NOTE: outputs might already have been produced before we started listening for this
            # event (or the count might genuinely differ); the UI-based check below is authoritative
            pass

    with log_context(logging.INFO, f"Checking node {node_id=} outputs"):
        path_filter = f"{study_id}/{node_id}"
        with page.expect_response(re.compile(r"storage/locations/0/paths\?file_filter="), timeout=30 * SECOND):
            if app_mode:
                page.get_by_test_id("outputsBtn").click()
            page.get_by_test_id("nodeFilesBtn").click()

        page.get_by_test_id("folderGridView").click()
        items = page.get_by_test_id("FolderViewerItem")

        if open_outputs_folder:
            outputs_found = False
            for index in range(items.count()):
                item = items.nth(index)
                if "output" in (item.text_content() or ""):
                    item.dblclick()
                    outputs_found = True
            assert outputs_found, f"outputs folder not found for node {node_id} ({path_filter})"
            items = page.get_by_test_id("FolderViewerItem")

        actual_file_names = [(name or "").removesuffix("\ue24d") for name in items.all_text_contents()]
        page.get_by_test_id("nodeDataManagerCloseBtn").click()

        assert len(actual_file_names) == len(expected_file_names), (
            f"Expected {len(expected_file_names)} file(s) {expected_file_names}, "
            f"got {len(actual_file_names)} {actual_file_names}"
        )


def run_pipeline_and_wait_done(
    page: Page,
    websocket: RobustWebSocket,
    *,
    run_button_test_id: str = "runStudyBtn",
    timeout_ms: int = _RUN_PIPELINE_MAX_WAIT_TIME,
) -> RunningState:
    """Clicks the "Run" button and waits until the pipeline reaches a final state.

    Port of the legacy `TutorialBase.runPipeline()` + `TutorialBase.waitForStudyDone()`.
    """
    waiter = SocketIOProjectStateUpdatedWaiter(
        expected_states=(RunningState.SUCCESS, RunningState.FAILED, RunningState.ABORTED)
    )
    with log_context(
        logging.INFO,
        f"Running pipeline and waiting for it to complete (timeout {datetime.timedelta(milliseconds=timeout_ms)})",
    ):
        with websocket.expect_event("framereceived", waiter, timeout=timeout_ms) as event:
            page.get_by_test_id(run_button_test_id).click()
        current_state = retrieve_project_state_from_decoded_message(decode_socketio_42_message(event.value))
        assert current_state == RunningState.SUCCESS, f"❌ Pipeline finished with {current_state} ❌"
        return current_state


def wait_for_voila_iframe(page: Page, node_id: str, *, timeout_ms: int = _VOILA_IFRAME_MAX_WAIT_TIME) -> FrameLocator:
    """Waits for the Voila iframe to appear (it can take a while to render).

    Port of `TutorialBase.waitForVoilaIframe()`.
    """
    iframe_locator = page.frame_locator(f'[osparc-test-id="iframe_{node_id}"]')
    with log_context(logging.INFO, f"Waiting for Voila iframe of node {node_id=}"):
        page.locator(f'[osparc-test-id="iframe_{node_id}"]').wait_for(state="attached", timeout=timeout_ms)
    return iframe_locator


def wait_for_voila_rendered(iframe_locator: FrameLocator, *, timeout_ms: int = _VOILA_RENDERED_MAX_WAIT_TIME) -> None:
    """Waits until the Voila notebook has finished rendering.

    Port of `TutorialBase.waitForVoilaRendered()`.
    """
    with log_context(logging.INFO, "Waiting for Voila to render"):
        iframe_locator.locator("#rendered_cells").wait_for(state="visible", timeout=timeout_ms)
