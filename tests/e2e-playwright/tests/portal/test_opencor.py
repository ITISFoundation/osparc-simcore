# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

"""Port of the legacy tests/e2e/portal/opencor.js Puppeteer script."""

from collections.abc import Callable
from typing import Any

from playwright.sync_api import Page
from pytest_simcore.helpers.playwright import check_node_outputs, run_pipeline_and_wait_done


def test_opencor(
    page: Page,
    open_study_link: Callable[..., Any],
    anonymous_study_url: str,
    run_pipeline_timeout: int,
) -> None:
    url = f"{anonymous_study_url}?stimulation_mode=1&stimulation_level=0.5"
    opened_study = open_study_link(url)
    study_id = opened_study.project_data["uuid"]

    run_pipeline_and_wait_done(page, opened_study.websocket, timeout_ms=run_pipeline_timeout)

    check_node_outputs(
        page,
        study_id=study_id,
        node_position=0,
        expected_file_names=["results.json", "logs.zip", "membrane-potential.csv"],
    )
