# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

"""Port of the legacy tests/e2e/portal/CC_Human.js Puppeteer script."""

from collections.abc import Callable
from typing import Any

from playwright.sync_api import Page
from pytest_simcore.helpers.playwright import check_node_outputs, run_pipeline_and_wait_done


def test_cc_human(
    page: Page,
    open_study_link: Callable[..., Any],
    anonymous_study_url: str,
    run_pipeline_timeout: int,
) -> None:
    opened_study = open_study_link(anonymous_study_url)
    study_id = opened_study.project_data["uuid"]

    run_pipeline_and_wait_done(page, opened_study.websocket, timeout_ms=run_pipeline_timeout)

    check_node_outputs(
        page,
        study_id=study_id,
        node_position=1,
        expected_file_names=["vm_1Hz.txt", "logs.zip", "allresult_1Hz.txt"],
    )
    check_node_outputs(
        page,
        study_id=study_id,
        node_position=2,
        expected_file_names=["model_INPUT.from1D", "y_1D.txt", "logs.zip", "ECGs.txt"],
    )
    check_node_outputs(
        page,
        study_id=study_id,
        node_position=3,
        expected_file_names=["aps.zip", "logs.zip"],
    )
