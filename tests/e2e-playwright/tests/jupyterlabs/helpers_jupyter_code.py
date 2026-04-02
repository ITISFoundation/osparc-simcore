import logging
import re
from datetime import timedelta
from pathlib import Path
from typing import Final

from _jupyter_cell_code import ALL_PHASES, COMPLETE_MARKER, FAIL_MARKER
from playwright.sync_api import FrameLocator, expect
from pydantic import ByteSize
from pytest_simcore.helpers.logging_tools import log_context
from pytest_simcore.helpers.playwright import SECOND

_IDLE_TIMEOUT_MS: Final[int] = 60 * SECOND

_JUPYTER_CELL_CODE_PATH: Final[Path] = Path(__file__).parent / "_jupyter_cell_code.py"


def _execute_cell_and_wait_for_marker(iframe: FrameLocator, code: str, phase_label: str, timeout: int) -> None:
    """Fill a new cell with *code*, execute it and wait for COMPLETE_MARKER."""
    with log_context(
        logging.INFO, f"▶️ executing '{phase_label}' expected max duration '{timedelta(milliseconds=timeout)}'"
    ):
        cell = iframe.get_by_label("Untitled.ipynb").get_by_role("textbox").last
        cell.fill(code)
        cell.press("Shift+Enter")

        output_locator = iframe.locator(".jp-OutputArea-output").last
        expect(output_locator).to_contain_text(COMPLETE_MARKER, timeout=timeout)
        expect(output_locator).not_to_contain_text(FAIL_MARKER)

        # scroll the notebook so the latest output is visible
        output_locator.scroll_into_view_if_needed()


def _replace_line_with_prefix(s: str, prefix: str, replacement: str) -> str:
    pattern = r"^" + re.escape(prefix) + r".*$"
    return re.sub(pattern, replacement, s, flags=re.MULTILINE)


def create_files_in_jupyter(iframe: FrameLocator, large_file_size: ByteSize, large_file_block_size: ByteSize) -> None:
    with log_context(logging.INFO, "running rclone stress test"):
        iframe.get_by_role("button", name="New Launcher").nth(0).click()
        iframe.locator(".jp-LauncherCard-icon").first.click()
        iframe.get_by_role("tab", name="Untitled.ipynb").click()

        # wait for the kernel to be fully initialized before interacting
        with log_context(logging.INFO, "waiting for kernel to be fully initialized"):
            expect(iframe.get_by_text("Fully initialized")).to_be_visible(timeout=_IDLE_TIMEOUT_MS)

        # first cell: load all definitions (imports, config, helpers, phase functions)
        preamble_code = _JUPYTER_CELL_CODE_PATH.read_text()
        preamble_code = _replace_line_with_prefix(
            preamble_code,
            "LARGE_FILE_MAX_BYTES: Final[int] =",
            f"LARGE_FILE_MAX_BYTES: Final[int] = {large_file_size}",
        )
        preamble_code = _replace_line_with_prefix(
            preamble_code,
            "LARGE_FILE_WRITE_CHUNK: Final[int] =",
            f"LARGE_FILE_WRITE_CHUNK: Final[int] = {large_file_block_size}",
        )
        with log_context(logging.INFO, "loading preamble (definitions)"):
            cell = iframe.get_by_label("Untitled.ipynb").get_by_role("textbox").last
            cell.fill(preamble_code)
            cell.press("Shift+Enter")

        # execute each phase in its own cell
        for phase_func_name, timeout in ALL_PHASES:
            _execute_cell_and_wait_for_marker(
                iframe,
                code=f"{phase_func_name}()",
                phase_label=phase_func_name,
                timeout=timeout,
            )

        # rename the notebook so "Untitled.ipynb" is free for subsequent notebooks
        with log_context(logging.INFO, "renaming notebook"):
            iframe.get_by_role("tab", name="Untitled.ipynb").click(button="right")
            iframe.get_by_text("Rename Notebook").click()
            name_input = iframe.locator(".jp-Dialog input")
            name_input.fill("files_creation.ipynb")
            iframe.get_by_role("button", name="Rename").click()
