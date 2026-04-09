# pylint: disable=redefined-outer-name
import logging
import re
from collections.abc import Callable
from typing import Any, Final

import pytest
from playwright.sync_api import Page, expect
from pytest_simcore.helpers.logging_tools import log_context
from pytest_simcore.helpers.playwright import SECOND, RunningState

_OPEN_WAIT_TIME: Final[int] = 20 * SECOND


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
    create_new_project_and_delete: Callable[[tuple[RunningState], bool, str | None, str | None], dict[str, Any]],
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


def open_project_from_dashboard(page: Page, start_project_uuid: str) -> None:
    with page.expect_response(re.compile(r"/projects/[^:]+:open"), timeout=_OPEN_WAIT_TIME) as response_info:
        card_id = "studyBrowserListItem_" + start_project_uuid
        page.get_by_test_id(card_id).click()
        open_button = page.get_by_test_id("openResource")
        expect(open_button).to_be_visible(timeout=_OPEN_WAIT_TIME)
        open_button.click()
    assert response_info.value.ok, f"{response_info.value.json()}"
    return response_info.value.json()["data"]
