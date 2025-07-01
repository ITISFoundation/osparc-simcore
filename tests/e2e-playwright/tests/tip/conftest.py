# pylint: disable=redefined-outer-name
import logging
from collections.abc import Callable
from typing import Any

import pytest
from playwright.sync_api import Page
from pytest_simcore.helpers.logging_tools import log_context
from pytest_simcore.helpers.playwright import RunningState


@pytest.fixture
def find_and_start_tip_plan_in_dashboard(
    page: Page,
) -> Callable[[str], None]:
    def _(
        plan_name_test_id: str,
    ) -> None:
        with log_context(logging.INFO, f"Finding {plan_name_test_id=} in dashboard"):
            page.get_by_test_id("newPlansBtn").click()
            page.get_by_test_id(plan_name_test_id).click()

    return _


@pytest.fixture
def create_tip_plan_from_dashboard(
    find_and_start_tip_plan_in_dashboard: Callable[[str], None],
    create_new_project_and_delete: Callable[
        [tuple[RunningState], bool, str | None, str | None], dict[str, Any]
    ],
) -> Callable[[str], dict[str, Any]]:
    def _(plan_name_test_id: str) -> dict[str, Any]:
        find_and_start_tip_plan_in_dashboard(plan_name_test_id)
        expected_states = (RunningState.NOT_STARTED,)
        return create_new_project_and_delete(
            expected_states,
            False,  # noqa: FBT003
            None,
            None,
        )

    return _
