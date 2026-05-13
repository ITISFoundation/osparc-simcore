import logging
import re
from datetime import timedelta
from pathlib import Path
from typing import Final

from _jupyter_cell_code import ALL_PHASES, COMPLETE_MARKER, FAIL_MARKER
from playwright.sync_api import FrameLocator, Locator, expect
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from pydantic import ByteSize
from pytest_simcore.helpers.datetime_tools import timedelta_as_minute_second_ms
from pytest_simcore.helpers.logging_tools import log_context
from pytest_simcore.helpers.playwright import SECOND

_IDLE_TIMEOUT_MS: Final[int] = 60 * SECOND
_DISMISS_DIALOG_POLL_MS: Final[int] = 2 * SECOND

_JUPYTER_CELL_CODE_PATH: Final[Path] = Path(__file__).parent / "_jupyter_cell_code.py"


def _dismiss_dialogs(iframe: FrameLocator) -> None:
    """Dismiss any JupyterLab modal dialogs (e.g. 'File Changed') that may pop up."""
    dialog = iframe.locator(".jp-Dialog")
    if dialog.count() == 0:
        return

    for btn_name in ("Dismiss", "OK", "Overwrite", "Revert"):
        btn = dialog.locator(f".jp-mod-accept:has-text('{btn_name}')")
        if btn.count() > 0:
            btn.first.click()
            return


def _expect_with_dialog_dismissal(iframe: FrameLocator, output_locator: Locator, timeout: int) -> None:
    """Wait for *COMPLETE_MARKER* while periodically dismissing JupyterLab dialogs.

    Playwright sync API is not thread-safe, so we poll on the main thread:
    try a short ``expect`` wait, dismiss any dialogs, repeat until the
    total *timeout* (ms) is exhausted.
    """
    remaining = timeout
    last_error: AssertionError | PlaywrightTimeoutError | None = None
    while remaining > 0:
        wait_slice = min(_DISMISS_DIALOG_POLL_MS, remaining)
        try:
            expect(output_locator).to_contain_text(COMPLETE_MARKER, timeout=wait_slice)
            return
        except (AssertionError, PlaywrightTimeoutError) as error:
            last_error = error
            remaining -= wait_slice
            if remaining > 0:
                _dismiss_dialogs(iframe)

    if last_error is not None:
        raise last_error


def _execute_cell_and_wait_for_marker(iframe: FrameLocator, code: str, phase_label: str, timeout: int) -> None:
    """Fill a new cell with *code*, execute it and wait for COMPLETE_MARKER."""
    with log_context(
        logging.INFO,
        f"▶️ executing '{phase_label}' expected max duration "
        f"'{timedelta_as_minute_second_ms(timedelta(milliseconds=timeout))}'",
    ):
        # count existing outputs so we can target the new cell's output by index
        output_count_before = iframe.locator(".jp-OutputArea-output").count()

        _dismiss_dialogs(iframe)

        cell = iframe.get_by_label("files_creation.ipynb").get_by_role("textbox").last
        cell.fill(code)
        cell.press("Shift+Enter")

        output_locator = iframe.locator(".jp-OutputArea-output").nth(output_count_before)

        _expect_with_dialog_dismissal(iframe, output_locator, timeout)

        _dismiss_dialogs(iframe)

        expect(output_locator).not_to_contain_text(FAIL_MARKER)

        # scroll the notebook so the latest output is visible
        output_locator.scroll_into_view_if_needed()

        _dismiss_dialogs(iframe)


def _replace_line(s: str, line_start_with: str, replace_with: str) -> str:
    pattern = r"^" + re.escape(line_start_with) + r".*$"
    return re.sub(pattern, replace_with, s, flags=re.MULTILINE)


def create_files_in_jupyter(iframe: FrameLocator, large_file_size: ByteSize, large_file_block_size: ByteSize) -> None:
    with log_context(logging.INFO, "running files test"):
        iframe.get_by_role("button", name="New Launcher").nth(0).click()
        iframe.locator(".jp-LauncherCard-icon").first.click()
        iframe.get_by_role("tab", name="Untitled.ipynb").click()

        # rename the notebook so "Untitled.ipynb" is free for subsequent notebooks
        with log_context(logging.INFO, "renaming notebook"):
            iframe.get_by_role("tab", name="Untitled.ipynb").click(button="right")
            iframe.get_by_text("Rename Notebook").click()
            name_input = iframe.locator(".jp-Dialog input")
            name_input.fill("files_creation.ipynb")
            iframe.get_by_role("button", name="Rename").click()

        # wait for the kernel to be fully initialized before interacting
        with log_context(logging.INFO, "waiting for kernel to be fully initialized"):
            expect(iframe.get_by_text("Fully initialized")).to_be_visible(timeout=_IDLE_TIMEOUT_MS)

        # first cell: load all definitions (imports, config, helpers, phase functions)
        preamble_code = _JUPYTER_CELL_CODE_PATH.read_text()
        for line_start_with, replace_with in (
            (
                "LARGE_FILE_MAX_BYTES: Final[int] =",
                f"LARGE_FILE_MAX_BYTES: Final[int] = {large_file_size}",
            ),
            (
                "LARGE_FILE_WRITE_CHUNK: Final[int] =",
                f"LARGE_FILE_WRITE_CHUNK: Final[int] = {large_file_block_size}",
            ),
        ):
            preamble_code = _replace_line(preamble_code, line_start_with, replace_with)

        with log_context(logging.INFO, "loading preamble (definitions)"):
            cell = iframe.get_by_label("files_creation.ipynb").get_by_role("textbox").last
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

        _dismiss_dialogs(iframe)
