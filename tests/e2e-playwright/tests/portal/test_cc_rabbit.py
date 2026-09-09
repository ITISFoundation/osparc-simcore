# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument


from collections.abc import Callable
from typing import Any

from playwright.sync_api import Page
from pytest_simcore.helpers.playwright import check_node_outputs, run_pipeline_and_wait_done


def test_cc_rabbit(
    page: Page,
    open_study_link: Callable[..., Any],
    anonymous_study_url: str,
    run_pipeline_timeout: int,
) -> None:
    opened_study = open_study_link(anonymous_study_url)
    project_data = opened_study.project_data
    study_id = project_data["uuid"]
    workbench = project_data["workbench"]

    run_pipeline_and_wait_done(page, opened_study.websocket, timeout_ms=run_pipeline_timeout)

    check_node_outputs(
        page,
        study_id=study_id,
        workbench=workbench,
        node_name="Rabbit SS 0D cardiac model",
        expected_file_names=["logs.zip", "allresult_1Hz.txt", "vm_1Hz.txt"],
    )
    check_node_outputs(
        page,
        study_id=study_id,
        workbench=workbench,
        node_name="Rabbit SS 1D cardiac model",
        expected_file_names=["model_INPUT.from1D", "logs.zip", "cai_1D.txt", "ap_1D.txt", "ECGs.txt"],
    )
    check_node_outputs(
        page,
        study_id=study_id,
        workbench=workbench,
        node_name="Rabbit SS 2D cardiac model",
        expected_file_names=["aps.zip", "logs.zip"],
    )
