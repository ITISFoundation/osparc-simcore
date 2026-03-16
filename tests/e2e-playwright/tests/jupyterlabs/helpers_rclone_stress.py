import logging
from pathlib import Path
from typing import Final

from playwright.sync_api import FrameLocator, expect
from pytest_simcore.helpers.logging_tools import log_context
from pytest_simcore.helpers.playwright import MINUTE, SECOND

_JUPYTER_CELL_CODE_PATH: Final[Path] = Path(__file__).parent / "_jupyter_cell_code.py"
_IDLE_TIMEOUT_MS: Final[int] = 60 * SECOND
_CELL_EXECUTION_TIMEOUT_MS: Final[int] = 2 * MINUTE


def execute_rclone_stress(iframe: FrameLocator) -> None:
    with log_context(logging.INFO, "running rclone stress test"):
        iframe.get_by_role("button", name="New Launcher").nth(0).click()
        iframe.locator(".jp-LauncherCard-icon").first.click()
        iframe.get_by_role("tab", name="Untitled.ipynb").click()

        # wait for the kernel to be fully initialized before interacting
        with log_context(logging.INFO, "waiting for kernel to be fully initialized"):
            expect(iframe.get_by_text("Fully initialized")).to_be_visible(timeout=_IDLE_TIMEOUT_MS)

        _jupyterlab_ui = iframe.get_by_label("Untitled.ipynb").get_by_role("textbox")

        cell_code = _JUPYTER_CELL_CODE_PATH.read_text()
        cell_code += "\n\n_code_to_go_in_the_cell()\n"
        _jupyterlab_ui.fill(cell_code)
        _jupyterlab_ui.press("Shift+Enter")

        # wait for the cell to finish executing by checking the output area
        output_locator = iframe.locator(".jp-OutputArea-output")
        expect(output_locator).to_contain_text(
            "done sleeping, now I am really done",
            timeout=_CELL_EXECUTION_TIMEOUT_MS,
        )
