"""Shared UI steps for the TIP plan tests (test_ti_plan / test_ti_personalized_plan)."""

import logging

from playwright.sync_api import FrameLocator, expect
from pytest_simcore.helpers.logging_tools import log_context


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
