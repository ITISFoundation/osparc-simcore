# pylint: disable=redefined-outer-name
import logging
from collections.abc import Callable
from typing import Any

import pytest
from playwright.sync_api import Page
from pytest_simcore.logging_utils import log_context
from pytest_simcore.playwright_utils import RunningState


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup(
        "oSparc e2e options", description="oSPARC-e2e specific parameters"
    )
    group.addoption(
        "--service-opening-waiting-timeout",
        action="store",
        type=int,
        default=300000,  # 5 mins
        help="Defines a waiting timeout in milliseconds for opening a service.",
    )


@pytest.fixture
def service_opening_waiting_timeout(request: pytest.FixtureRequest) -> int:
    service_opening_waiting_timeout = request.config.getoption(
        "--service-opening-waiting-timeout"
    )
    assert isinstance(service_opening_waiting_timeout, int)
    return service_opening_waiting_timeout


@pytest.fixture
def find_and_start_tip_plan_in_dashboard(
    page: Page,
) -> Callable[[str], None]:
    def _(
        plan_name_test_id: str,
    ) -> None:
        with log_context(logging.INFO, f"Finding {plan_name_test_id=} in dashboard"):
            page.get_by_test_id("studiesTabBtn").click()
            page.get_by_test_id("newStudyBtn").click()
            page.get_by_test_id(plan_name_test_id).click()

    return _


@pytest.fixture
def create_tip_plan_from_dashboard(
    find_and_start_tip_plan_in_dashboard: Callable[[str], None],
    create_new_project_and_delete: Callable[
        [tuple[RunningState], bool], dict[str, Any]
    ],
) -> Callable[[str], dict[str, Any]]:
    def _(plan_name_test_id: str) -> dict[str, Any]:
        find_and_start_tip_plan_in_dashboard(plan_name_test_id)
        expected_states = (RunningState.UNKNOWN,)
        return create_new_project_and_delete(expected_states, press_open=False)

    return _
