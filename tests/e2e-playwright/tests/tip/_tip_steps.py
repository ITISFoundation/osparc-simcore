"""Shared UI steps for the TIP plan tests (test_ti_plan / test_ti_personalized_plan)."""

import contextlib
import logging
from typing import Final

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import FrameLocator, Locator, expect
from pytest_simcore.helpers.logging_tools import log_context
from pytest_simcore.helpers.playwright import (
    MINUTE,
    SECOND,
)
from tenacity import RetryError, Retrying, retry, retry_if_result, stop_after_delay, wait_fixed

_EC2_STARTUP_MAX_WAIT_TIME: Final[int] = 1 * MINUTE
POST_PRO_MAX_STARTUP_TIME: Final[int] = 5 * MINUTE
_POST_PRO_DOCKER_PULLING_MAX_TIME: Final[int] = 20 * MINUTE
POST_PRO_AUTOSCALED_MAX_STARTUP_TIME: Final[int] = (
    _EC2_STARTUP_MAX_WAIT_TIME + _POST_PRO_DOCKER_PULLING_MAX_TIME + POST_PRO_MAX_STARTUP_TIME
)
POST_PRO_TARGET_TISSUE_APPEARANCE_TIME: Final[int] = 10 * MINUTE
POST_PRO_LOAD_APPEARANCE_TIME: Final[int] = 5 * MINUTE
POST_PRO_RUN_OPTIMIZATION_MAX_TIME: Final[int] = 25 * MINUTE
POST_PRO_LOAD_ANALYSIS_MAX_TIME: Final[int] = 5 * MINUTE
POST_PRO_LOAD_RESULT_MAX_TIME: Final[int] = 30 * SECOND
POST_PRO_REPORTING_MAX_TIME: Final[int] = 30 * SECOND


def get_node_id_from_service_key(workbench: dict, service_key: str) -> str:
    """Returns the node id of the node whose service key equals ``service_key``.

    The nodes' position in the workbench is not guaranteed, so steps must be
    resolved by their service key instead of by their index.
    """
    matches = [node_id for node_id, node_data in workbench.items() if node_data.get("key", "") == service_key]
    if len(matches) != 1:
        msg = f"Expected exactly 1 node with service key {service_key!r} in the workbench, found {len(matches)}"
        raise ValueError(msg)
    return matches[0]


def raise_if_button_spinner_running(button: Locator, *, description: str) -> None:
    """Raises ``ValueError`` while the button still shows a ``fa-spinner`` icon
    (i.e. the operation is in progress), and returns quietly once the icon is gone.

    Meant to be wrapped by a ``tenacity.retry`` with the appropriate timeout.
    """
    try:
        icon_class = button.locator("i").first.evaluate("el => el.className")
    except PlaywrightError:
        logging.info("%s button icon not found — operation likely completed", description)
        return
    if "fa-spinner" in icon_class:
        msg = f"{description} still running: {icon_class=}"
        raise ValueError(msg)


@retry(
    stop=stop_after_delay(POST_PRO_REPORTING_MAX_TIME / 1000),  # seconds
    wait=wait_fixed(10),
    reraise=True,
)
def wait_for_export_complete(button: Locator) -> None:
    """Wait for an export button to finish by checking the fa-spinner icon."""
    raise_if_button_spinner_running(button, description="Export")


def wait_and_select_target_tissue(
    ti_iframe: FrameLocator,
    *,
    label_timeout: int,
    select_timeout: int | None = None,
) -> None:
    """Waits for the TI UI to load and selects the first non-empty target tissue."""
    with log_context(logging.INFO, "Wait for UI to load"):
        target_tissue_label = ti_iframe.get_by_text("Target tissue:")
        expect(target_tissue_label).to_be_visible(timeout=label_timeout)

    with log_context(logging.INFO, "Select Target tissue"):
        target_tissue_select = ti_iframe.get_by_label("Target tissue")
        expect(target_tissue_select).to_be_visible(timeout=select_timeout)
        # Pick the first non-empty option
        options = target_tissue_select.locator("option").all()
        selected = False
        for option in options:
            value = option.get_attribute("value") or ""
            if value.strip():
                target_tissue_select.select_option(value=value)
                logging.info("Selected target tissue: %s", option.inner_text())
                selected = True
                break
        assert selected, "No non-empty target tissue option found"


def set_fast_optimization_settings(ti_iframe: FrameLocator) -> None:
    """Configures the optimization to run as fast as possible:
    'Low' convergence and the minimum number of 'Max Iterations' (10)."""
    with log_context(logging.INFO, "Select 'Low' Convergence"):
        ti_iframe.get_by_role("button", name="Low").click()

    with log_context(logging.INFO, "Reduce 'Max Iterations' to the minimum (10)"):
        max_iterations_input = ti_iframe.get_by_label("Max Iterations")
        expect(max_iterations_input).to_be_visible()
        max_iterations_input.fill("1")  # it will be increased to 10 by the app, which is the minimum allowed


def _is_button_busy(button: Locator, *, consider_disabled: bool) -> bool:
    """A button is considered 'busy' while it shows a ``fa-spinner`` icon and,
    when ``consider_disabled`` is set, while it is disabled."""
    if consider_disabled and not button.is_enabled():
        return True
    try:
        icon_class = button.locator("i").first.evaluate("el => el.className")
    except PlaywrightError:
        return False
    return "fa-spinner" in icon_class


def _click_and_wait_until_idle(
    button: Locator,
    *,
    description: str,
    click_timeout: int,
    idle_timeout: int,
    start_timeout: int = 10 * SECOND,
    poll_interval: int = 10,
    consider_disabled: bool = False,
) -> None:
    """Clicks a button and waits until the triggered operation completes.

    Completion is detected by the button becoming idle (no ``fa-spinner`` icon and,
    when ``consider_disabled`` is set, enabled again). To avoid reading a premature
    "idle" state right after the click, it first waits (best-effort) for the button
    to enter the busy state.
    """

    def _busy() -> bool:
        return _is_button_busy(button, consider_disabled=consider_disabled)

    with log_context(logging.INFO, f"Click `{description}`"):
        button.click(timeout=click_timeout)

    # best-effort: if it never appears busy we assume it already completed
    with log_context(logging.INFO, f"Wait for `{description}` to start"), contextlib.suppress(RetryError):
        Retrying(
            stop=stop_after_delay(start_timeout / 1000),
            wait=wait_fixed(1),
            retry=retry_if_result(lambda busy: busy is False),
        )(_busy)

    with log_context(logging.INFO, f"Wait for `{description}` to complete"):
        Retrying(
            stop=stop_after_delay(idle_timeout / 1000),
            wait=wait_fixed(poll_interval),
            retry=retry_if_result(lambda busy: busy is True),
            reraise=True,
        )(_busy)


def run_optimization_and_load_analysis(
    ti_iframe: FrameLocator,
    *,
    click_timeout: int,
    optimization_timeout: int,
    optimization_start_timeout: int,
    analysis_timeout: int,
    result_timeout: int,
) -> None:
    """Shared TI flow: click `Run Optimization`, `Load Analysis` and `Load`,
    waiting for each operation to finish before clicking the next one."""
    _click_and_wait_until_idle(
        ti_iframe.get_by_role("button", name="Run Optimization"),
        description="Run Optimization",
        click_timeout=click_timeout,
        idle_timeout=optimization_timeout,
        start_timeout=optimization_start_timeout,
        # the optimization button gets disabled while running and re-enabled when done
        consider_disabled=True,
    )
    _click_and_wait_until_idle(
        ti_iframe.get_by_role("button", name="Load Analysis"),
        description="Load Analysis",
        click_timeout=click_timeout,
        idle_timeout=analysis_timeout,
    )
    # nth(0) is the Settings "Load" button at the top; nth(1) might be Load Analysis, so go with nth(2)
    _click_and_wait_until_idle(
        ti_iframe.get_by_role("button", name="Load", exact=True).nth(2),
        description="Load",
        click_timeout=click_timeout,
        idle_timeout=result_timeout,
    )
